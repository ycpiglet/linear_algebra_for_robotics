#!/usr/bin/env python3
"""Editorial bridge: resolve suggestion issues to .qmd sources and record events.

Phase 1-3 + 3-1 of EDITING_SYSTEM_PLAN.md.  The review build's suggestion
panel files GitHub issues whose body carries a machine-readable
``<!-- editorial-anchor {...} -->`` payload (page URL, paragraph id, quote,
30-char prefix/suffix).  This tool:

- ``fetch``   pulls open ``editorial``-labeled issues (``--count-only`` is the
  zero-token pre-filter of §5.6 — the digest workflow exits early on 0).
- ``apply``   maps each issue to its .qmd source, applies unambiguous
  plain-text suggestions (one commit per correction, §5.4), appends an
  editorial event record (§6), and reports everything it could not apply
  (ambiguous, markup-crossing, comment-only) with the resolved source
  location so a human or LLM pass can pick it up.
- ``ingest``  validates and appends a single event record.

Only exact, markup-free text spans are auto-applied — the same selectivity
Acrobat uses when exporting "text edits only" back to a Word source; anything
else is surfaced for review instead of guessed at.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = Path("platform/editorial/events")
SCHEMA = Path("platform/schemas/editorial-event.schema.json")
DEFAULT_LABEL = "editorial"
PROCESSED_LABEL = "bridged"
AGENT_ACTOR = "agent:editorial-bridge"
GIT_AUTHOR = "editorial-bridge <editorial-bridge@users.noreply.github.com>"

ANCHOR_RE = re.compile(r"<!--\s*editorial-anchor\s+(\{.*?\})\s*-->", re.S)
_MARKUP_CHARS = set("*_`")


# ---------------------------------------------------------------------------
# Issue parsing


@dataclass
class Proposal:
    number: int
    title: str
    author: str
    page: str
    paragraph_id: str | None
    quote: str
    prefix: str
    suffix: str
    suggestion: str
    comment: str


def _section(body: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |^<!-- |\Z)",
        body,
        re.M | re.S,
    )
    return match.group(1).strip() if match else ""


def _fenced(text: str) -> str:
    match = re.search(r"^~~~\n(.*?)\n~~~\s*$", text, re.S | re.M)
    return match.group(1) if match else ""


def parse_issue(issue: dict[str, Any]) -> Proposal | None:
    """Extract the anchor payload and human sections; None if not ours."""
    body = issue.get("body") or ""
    match = ANCHOR_RE.search(body)
    if not match:
        return None
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    quote = meta.get("quote") or ""
    if not quote:
        return None
    return Proposal(
        number=issue["number"],
        title=issue.get("title") or "",
        author=(issue.get("user") or {}).get("login", "unknown"),
        page=meta.get("page") or "",
        paragraph_id=meta.get("paragraph"),
        quote=quote,
        prefix=meta.get("prefix") or "",
        suffix=meta.get("suffix") or "",
        suggestion=_fenced(_section(body, "수정안")),
        comment=_section(body, "사유·코멘트"),
    )


# ---------------------------------------------------------------------------
# Source mapping


def page_to_source(page: str, root: Path = ROOT) -> Path | None:
    """Map a rendered page URL to its .qmd source.

    Leading path segments (site subpath, /review/, /preview/pr-N/) are
    stripped progressively until the remainder matches an existing source.
    """
    path = urllib.parse.urlsplit(page).path
    if path.endswith("/"):
        path += "index.html"
    if not path.endswith(".html"):
        return None
    parts = [part for part in path.split("/") if part]
    for start in range(len(parts)):
        relative = "/".join(parts[start:])[: -len(".html")] + ".qmd"
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _normalized_with_map(raw: str) -> tuple[str, list[int]]:
    """Collapse whitespace and drop emphasis/code markers, keeping a map of
    each normalized character back to its raw offset."""
    out: list[str] = []
    positions: list[int] = []
    pending_space = False
    for index, char in enumerate(raw):
        if char.isspace():
            pending_space = bool(out)
            continue
        if char in _MARKUP_CHARS:
            continue
        if pending_space:
            out.append(" ")
            positions.append(index)
            pending_space = False
        out.append(char)
        positions.append(index)
    return "".join(out), positions


def locate(source: str, quote: str, prefix: str = "", suffix: str = "") -> list[tuple[int, int]]:
    """Return raw [start, end) spans of the rendered quote inside .qmd text.

    Multiple hits are disambiguated with the rendered prefix/suffix context
    (the same exact/prefix/suffix triple Hypothesis's TextQuoteSelector uses).
    """
    norm_source, positions = _normalized_with_map(source)
    norm_quote, _ = _normalized_with_map(quote)
    if not norm_quote:
        return []
    hits = [m.start() for m in re.finditer(re.escape(norm_quote), norm_source)]
    if len(hits) > 1 and (prefix or suffix):
        norm_prefix, _ = _normalized_with_map(prefix)
        norm_suffix, _ = _normalized_with_map(suffix)
        # 패널이 prefix/suffix를 trim해서 보내므로 경계의 공백 한 칸을 벗겨 비교한다.
        filtered = [
            hit
            for hit in hits
            if (not norm_prefix or norm_source[:hit].rstrip(" ").endswith(norm_prefix))
            and (not norm_suffix
                 or norm_source[hit + len(norm_quote):].lstrip(" ").startswith(norm_suffix))
        ]
        if filtered:
            hits = filtered
    spans = []
    for hit in hits:
        start = positions[hit]
        end = positions[hit + len(norm_quote) - 1] + 1
        spans.append((start, end))
    return spans


def replaceable(source: str, span: tuple[int, int]) -> bool:
    """Only plain prose spans are safe to rewrite mechanically.  A span that
    crosses inline markup or a paragraph boundary needs eyes, not a regex."""
    raw = source[span[0]:span[1]]
    if "\n\n" in raw:
        return False
    return not any(char in _MARKUP_CHARS for char in raw)


def line_of(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# Event records (§6)


def load_schema(root: Path = ROOT) -> dict[str, Any]:
    return json.loads((root / SCHEMA).read_text(encoding="utf-8"))


def validate_event(record: dict[str, Any], root: Path = ROOT) -> None:
    from jsonschema import Draft202012Validator

    errors = sorted(
        Draft202012Validator(load_schema(root)).iter_errors(record),
        key=lambda item: list(item.path),
    )
    if errors:
        messages = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise ValueError("Editorial event schema validation failed:\n" + "\n".join(messages))


def append_event(record: dict[str, Any], root: Path = ROOT) -> Path:
    validate_event(record, root)
    directory = root / EVENTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (record["date"][:7] + ".jsonl")
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target


# ---------------------------------------------------------------------------
# Apply


@dataclass
class Outcome:
    issue: int
    action: str  # applied | needs-review | comment-only | unmapped | not-found | ambiguous
    file: str | None = None
    line: int | None = None
    detail: str = ""
    event_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _event_for(proposal: Proposal, source: Path, status: str, after: str | None,
               root: Path, today: str) -> dict[str, Any]:
    return {
        "id": f"{today}-{source.stem}-i{proposal.number}",
        "date": today,
        "actor": AGENT_ACTOR,
        "actor_role": "agent",
        "target": {
            "file": str(source.relative_to(root)),
            "anchor_quote": proposal.quote,
            "anchor_context": [proposal.prefix, proposal.suffix],
            "paragraph_id": proposal.paragraph_id,
        },
        "category": None,
        "instruction": proposal.comment or proposal.title,
        "before": proposal.quote,
        "after": after,
        "rationale": None,
        "status": status,
        "links": {"source": f"issue:#{proposal.number}", "pr": None, "revert_of": None},
    }


def _git_commit(root: Path, paths: list[Path], message: str) -> str:
    subprocess.run(["git", "add", "--"] + [str(p) for p in paths], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "--author", GIT_AUTHOR, "-m", message],
        cwd=root,
        check=True,
        capture_output=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    return sha


def apply_issues(
    issues: list[dict[str, Any]],
    root: Path = ROOT,
    *,
    git: bool = True,
    dry_run: bool = False,
    today: str | None = None,
) -> list[Outcome]:
    today = today or _dt.date.today().isoformat()
    outcomes: list[Outcome] = []
    for issue in issues:
        proposal = parse_issue(issue)
        if proposal is None:
            continue
        source = page_to_source(proposal.page, root)
        if source is None:
            outcomes.append(Outcome(proposal.number, "unmapped",
                                    detail=f"페이지를 소스로 해석하지 못함: {proposal.page}"))
            continue
        text = source.read_text(encoding="utf-8")
        spans = locate(text, proposal.quote, proposal.prefix, proposal.suffix)
        relative = str(source.relative_to(root))
        if not spans:
            outcomes.append(Outcome(proposal.number, "not-found", file=relative,
                                    detail="원문 인용을 소스에서 찾지 못함"
                                           "(수식·링크 구간이거나 이미 수정됨)"))
            continue
        if len(spans) > 1:
            lines = ", ".join(str(line_of(text, s)) for s, _ in spans)
            outcomes.append(Outcome(proposal.number, "ambiguous", file=relative,
                                    detail=f"동일 문구가 여러 곳에 있음 (행 {lines})"))
            continue
        span = spans[0]
        line = line_of(text, span[0])
        if not proposal.suggestion:
            outcomes.append(Outcome(proposal.number, "comment-only", file=relative, line=line,
                                    detail="수정안 없는 코멘트 — 협의·LLM 경로로"))
            continue
        if not replaceable(text, span):
            outcomes.append(Outcome(proposal.number, "needs-review", file=relative, line=line,
                                    detail="인용 구간이 서식·문단 경계를 걸침 — 기계 반영 부적합"))
            continue

        outcome = Outcome(proposal.number, "applied", file=relative, line=line,
                          detail=f"'{proposal.quote[:30]}' → '{proposal.suggestion[:30]}'")
        if not dry_run:
            source.write_text(text[:span[0]] + proposal.suggestion + text[span[1]:],
                              encoding="utf-8")
            record = _event_for(proposal, source, "applied", proposal.suggestion, root, today)
            events_file = append_event(record, root)
            outcome.event_id = record["id"]
            if git:
                summary = (proposal.comment.splitlines()[0][:50]
                           if proposal.comment else proposal.quote[:30])
                sha = _git_commit(
                    root,
                    [source, events_file],
                    f"교정: {summary} (#{proposal.number})\n\n"
                    f"- 원문: {proposal.quote[:200]}\n"
                    f"- 수정: {proposal.suggestion[:200]}\n\n"
                    f"Issue: #{proposal.number}\nActor: agent",
                )
                outcome.extra["commit"] = sha
        outcomes.append(outcome)
    return outcomes


# ---------------------------------------------------------------------------
# Style lint (Phase 3-5) — machine-checkable rules promoted through §7

STYLE_RULES = Path("platform/editorial/style-rules.yml")
LINT_GLOBS = ("*.qmd", "content/**/*.qmd", "courseware/labs/*.qmd")


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    severity: str
    message: str
    excerpt: str


def load_rules(root: Path = ROOT) -> list[dict[str, Any]]:
    import yaml

    data = yaml.safe_load((root / STYLE_RULES).read_text(encoding="utf-8")) or {}
    rules = data.get("rules") or []
    for rule in rules:
        missing = {"id", "pattern", "message", "severity"} - rule.keys()
        if missing:
            raise ValueError(f"style rule missing fields {sorted(missing)}: {rule}")
        if rule["severity"] not in ("error", "warning"):
            raise ValueError(f"style rule severity must be error|warning: {rule['id']}")
        rule["_compiled"] = re.compile(rule["pattern"])
    return rules


def lint_text(text: str, rules: list[dict[str, Any]], file: str) -> list[Violation]:
    violations: list[Violation] = []
    in_code = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for rule in rules:
            match = rule["_compiled"].search(line)
            if match:
                violations.append(Violation(
                    file=file, line=line_number, rule=rule["id"],
                    severity=rule["severity"], message=rule["message"],
                    excerpt=line.strip()[:80],
                ))
    return violations


def lint_sources(root: Path = ROOT) -> list[Violation]:
    rules = load_rules(root)
    if not rules:
        return []
    violations: list[Violation] = []
    seen: set[Path] = set()
    for pattern in LINT_GLOBS:
        seen.update(root.glob(pattern))
    for path in sorted(seen):
        if path.is_file():
            violations.extend(
                lint_text(path.read_text(encoding="utf-8"), rules,
                          str(path.relative_to(root)))
            )
    return violations


# ---------------------------------------------------------------------------
# GitHub API (stdlib only)


def _github(path: str, token: str, method: str = "GET", payload: dict | None = None) -> Any:
    request = urllib.request.Request(
        "https://api.github.com" + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def count_pending(repo: str, token: str, label: str = DEFAULT_LABEL) -> int:
    query = urllib.parse.quote(
        f"repo:{repo} is:issue state:open label:{label} -label:{PROCESSED_LABEL}")
    return _github(f"/search/issues?q={query}&per_page=1", token)["total_count"]


def fetch_issues(repo: str, token: str, label: str = DEFAULT_LABEL) -> list[dict[str, Any]]:
    issues = _github(f"/repos/{repo}/issues?labels={label}&state=open&per_page=100", token)
    return [
        issue for issue in issues
        if "pull_request" not in issue
        and PROCESSED_LABEL not in {lab["name"] for lab in issue.get("labels", [])}
    ]


LABELS = [
    ("editorial", "1d76db", "리뷰 패널의 수정 제안 (브리지 수거 대상)"),
    ("bridged", "c5def5", "브리지가 처리함 — 자동 반영 또는 소스 위치 회신"),
    ("actor:agent", "0e8a16", "에이전트가 만든 변경 (§1-5 주체 구분)"),
    ("actor:supervisor", "5319e7", "감독자가 만든 변경 (§1-5 주체 구분)"),
    ("actor:editor", "fbca04", "외부 편집자가 만든 변경 (§1-5 주체 구분)"),
]


def setup_labels(repo: str, token: str) -> None:
    """Create the editorial label set; existing labels are left untouched."""
    import urllib.error

    for name, color, description in LABELS:
        try:
            _github(f"/repos/{repo}/labels", token, "POST",
                    {"name": name, "color": color, "description": description})
            print(f"created label: {name}", file=sys.stderr)
        except urllib.error.HTTPError as error:
            if error.code != 422:  # 422 = already exists
                raise
            print(f"label exists: {name}", file=sys.stderr)


def mark_processed(repo: str, token: str, outcome: Outcome) -> None:
    comments = {
        "applied": "🤖 자동 반영했습니다 — `{file}` {line}행, 커밋 `{commit}`. "
                   "배치 PR 병합 시 확정되며, 배치 리뷰에서 이 커밋만 revert로 기각할 수 있습니다.",
        "needs-review": "🤖 위치는 찾았지만(`{file}` {line}행) 인용 구간이 서식·문단 경계를 "
                        "걸쳐 자동 반영하지 않았습니다. 사람 검토가 필요합니다.",
        "comment-only": "🤖 소스 위치: `{file}` {line}행. "
                        "수정안이 없는 코멘트라 협의 경로로 넘깁니다.",
        "ambiguous": "🤖 같은 문구가 여러 곳에 있어 자동 반영하지 않았습니다. {detail} (`{file}`)",
        "not-found": "🤖 원문 인용을 소스(`{file}`)에서 찾지 못했습니다 — "
                     "이미 수정되었거나 수식·링크 구간일 수 있습니다.",
        "unmapped": "🤖 페이지 URL을 소스 파일로 해석하지 못했습니다: {detail}",
    }
    template = comments.get(outcome.action)
    if template:
        body = template.format(
            file=outcome.file or "?", line=outcome.line or "?",
            detail=outcome.detail, commit=outcome.extra.get("commit", "")[:10],
        )
        _github(f"/repos/{repo}/issues/{outcome.issue}/comments", token, "POST", {"body": body})
    _github(
        f"/repos/{repo}/issues/{outcome.issue}/labels", token, "POST",
        {"labels": [PROCESSED_LABEL]},
    )


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="open editorial issues -> JSON on stdout")
    fetch.add_argument("--repo", required=True)
    fetch.add_argument("--token", default=None, help="defaults to $GITHUB_TOKEN")
    fetch.add_argument("--count-only", action="store_true",
                       help="print pending count only (digest pre-filter)")

    apply_cmd = commands.add_parser("apply", help="apply suggestions from an issues JSON file")
    apply_cmd.add_argument("--issues", required=True, help="path to issues JSON ('-' for stdin)")
    apply_cmd.add_argument("--no-git", action="store_true")
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.add_argument("--repo", default=None,
                           help="when set with a token, comment on and label processed issues")
    apply_cmd.add_argument("--token", default=None)

    ingest = commands.add_parser("ingest", help="validate and append one event record")
    ingest.add_argument("--record", required=True, help="path to a JSON record ('-' for stdin)")

    labels = commands.add_parser("setup-labels", help="create the editorial label set (idempotent)")
    labels.add_argument("--repo", required=True)
    labels.add_argument("--token", default=None)

    commands.add_parser("lint", help="check manuscripts against promoted style rules")

    args = parser.parse_args(argv)
    import os

    if args.command == "fetch":
        token = args.token or os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN이 필요합니다", file=sys.stderr)
            return 2
        if args.count_only:
            print(count_pending(args.repo, token))
            return 0
        json.dump(fetch_issues(args.repo, token), sys.stdout, ensure_ascii=False)
        return 0

    if args.command == "apply":
        raw = (sys.stdin.read() if args.issues == "-"
               else Path(args.issues).read_text(encoding="utf-8"))
        issues = json.loads(raw)
        outcomes = apply_issues(issues, git=not args.no_git, dry_run=args.dry_run)
        token = args.token or os.environ.get("GITHUB_TOKEN", "")
        if args.repo and token and not args.dry_run:
            for outcome in outcomes:
                mark_processed(args.repo, token, outcome)
        json.dump([outcome.__dict__ for outcome in outcomes], sys.stdout,
                  ensure_ascii=False, indent=2, default=str)
        print()
        applied = sum(1 for o in outcomes if o.action == "applied")
        print(f"{len(outcomes)}건 처리, {applied}건 자동 반영", file=sys.stderr)
        return 0

    if args.command == "ingest":
        raw = (sys.stdin.read() if args.record == "-"
               else Path(args.record).read_text(encoding="utf-8"))
        target = append_event(json.loads(raw))
        print(f"appended to {target}", file=sys.stderr)
        return 0

    if args.command == "setup-labels":
        token = args.token or os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("GITHUB_TOKEN이 필요합니다", file=sys.stderr)
            return 2
        setup_labels(args.repo, token)
        return 0

    if args.command == "lint":
        violations = lint_sources()
        for violation in violations:
            print(f"{violation.file}:{violation.line} [{violation.severity}] "
                  f"{violation.rule}: {violation.message}\n    {violation.excerpt}")
        errors = sum(1 for v in violations if v.severity == "error")
        print(f"문체 규칙 위반 {len(violations)}건 (차단 {errors}건)", file=sys.stderr)
        return 1 if errors else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
