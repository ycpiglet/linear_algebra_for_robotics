#!/usr/bin/env python3
"""Verify actor provenance from a GitHub Actions event and the local Git graph.

The verifier is deliberately offline.  It trusts only an immutable Actions
event payload, a full local Git graph, and the repository-specific historical
cutline below.  New agent work must use canonical ``Actor: agent`` trailers;
history at or below the cutline is trusted without being rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_ACTORS = frozenset({"agent", "editor", "supervisor"})
ACTOR_LABELS = frozenset(f"actor:{actor}" for actor in ALLOWED_ACTORS)
TRUSTED_THROUGH = "37289c06a3c7752ef09d5348f4bc7b5e15bae291"
BOOTSTRAP_REF = "agent/pub-016-provenance-gate"
TRUSTED_GATE_PATHS = frozenset(
    {
        ".github/CODEOWNERS",
        ".github/workflows/provenance.yml",
        "CODEOWNERS",
        "docs/CODEOWNERS",
        "platform/editorial-runtime/pyproject.toml",
        "platform/editorial-runtime/uv.lock",
        "platform/scripts/verify_provenance.py",
        "platform/scripts/editorial.py",
        "platform/schemas/editorial-event.schema.json",
    }
)
BOOTSTRAP_CONTROL_PLANE_PATHS = frozenset(
    {
        ".github/workflows/editorial-digest.yml",
        ".github/workflows/provenance.yml",
        ".github/workflows/publish-web.yml",
        "platform/scripts/verify_provenance.py",
    }
)
ZERO_SHA = "0" * 40
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ACTOR_LIKE_LINE_RE = re.compile(r"^[ \t]*actor[ \t]*[:=]", re.IGNORECASE | re.MULTILINE)
CANONICAL_ACTOR_RE = re.compile(r"^Actor: (agent|editor|supervisor)$", re.MULTILINE)
ESCAPED_ACTOR_RE = re.compile(r"(?:(?:\\r)?\\n)+[ \t]*actor[ \t]*[:=]", re.IGNORECASE)


class ProvenanceError(RuntimeError):
    """Raised when provenance is missing, ambiguous, or structurally invalid."""


@dataclass(frozen=True)
class Verification:
    event: str
    commits: int
    actor: str | None = None


def _git(
    root: Path,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        input=input_text,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise ProvenanceError(f"git {' '.join(args)} failed: {detail}")
    return result


def _require_sha(root: Path, value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value) or value == ZERO_SHA:
        raise ProvenanceError(f"{field} must be a non-zero 40-character lowercase SHA")
    if _git(root, "cat-file", "-e", f"{value}^{{commit}}", check=False).returncode != 0:
        raise ProvenanceError(
            f"{field} commit is unavailable in the checked-out Git graph: {value}"
        )
    return value


def _commit_message(root: Path, commit: str) -> str:
    raw = subprocess.run(
        ["git", "cat-file", "commit", commit],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if raw.returncode != 0:
        detail = raw.stderr.decode("utf-8", errors="replace").strip() or "unknown Git error"
        raise ProvenanceError(f"git cat-file commit {commit} failed: {detail}")
    _, separator, message = raw.stdout.partition(b"\n\n")
    if not separator:
        raise ProvenanceError(f"{commit}: malformed commit object has no message separator")
    return message.decode("utf-8", errors="replace")


def _parsed_actor_lines(root: Path, message: str) -> list[str]:
    parsed = _git(
        root,
        "-c",
        "trailer.separators=:",
        "interpret-trailers",
        "--parse",
        "--no-divider",
        input_text=message,
    ).stdout
    return [
        line
        for line in parsed.splitlines()
        if line.partition(":")[0].strip().casefold() == "actor"
    ]


def _inspect_commit(root: Path, commit: str) -> str | None:
    message = _commit_message(root, commit)
    if ESCAPED_ACTOR_RE.search(message):
        raise ProvenanceError(f"{commit}: Actor marker contains a literal escaped newline")

    actor_like = ACTOR_LIKE_LINE_RE.findall(message)
    canonical = CANONICAL_ACTOR_RE.findall(message)
    parsed = _parsed_actor_lines(root, message)
    if not actor_like and not canonical and not parsed:
        return None
    if len(actor_like) != 1 or len(canonical) != 1 or len(parsed) != 1:
        raise ProvenanceError(
            f"{commit}: expected one canonical Actor trailer; found "
            f"{len(actor_like)} actor-like marker(s), {len(canonical)} canonical marker(s), "
            f"and {len(parsed)} parsed trailer(s)"
        )
    actor = canonical[0]
    if parsed[0] != f"Actor: {actor}":
        raise ProvenanceError(f"{commit}: Actor trailer is folded, noncanonical, or malformed")
    return actor


def _commits_not_in(root: Path, base: str, head: str, *, allow_empty: bool = False) -> list[str]:
    commits = _git(
        root,
        "rev-list",
        "--reverse",
        "--topo-order",
        head,
        "--not",
        base,
    ).stdout.splitlines()
    if not commits and not allow_empty:
        raise ProvenanceError(f"commit range is empty: {base}..{head}")
    return commits


def _changed_paths(root: Path, base: str, head: str) -> set[str]:
    # A three-dot diff asks Git to choose a merge base.  Criss-cross histories can
    # have several, and choosing only one can hide a control-plane tree change.
    # Comparing endpoint trees also avoids attributing trusted workflow changes
    # from a normal latest-main merge-sync to the older agent branch.
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", base, head],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProvenanceError(f"cannot determine pull request paths: {detail}")
    return {
        path.decode("utf-8", errors="replace")
        for path in result.stdout.split(b"\0")
        if path
    }


def _parents(root: Path, commit: str) -> list[str]:
    fields = _git(root, "rev-list", "--parents", "-n", "1", commit).stdout.split()
    if not fields or fields[0] != commit:
        raise ProvenanceError(f"cannot determine parents for {commit}")
    return fields[1:]


def _is_ancestor(root: Path, base: str, head: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", base, head, check=False).returncode == 0


def _is_first_parent_ancestor(root: Path, base: str, head: str) -> bool:
    return base in _git(root, "rev-list", "--first-parent", head).stdout.splitlines()


def _enforce_role(root: Path, commits: list[str], actor: str) -> None:
    for commit in commits:
        commit_actor = _inspect_commit(root, commit)
        if actor == "agent" and commit_actor != "agent":
            raise ProvenanceError(
                f"{commit}: actor:agent work requires exactly one canonical Actor: agent trailer"
            )
        if actor != "agent" and commit_actor not in {None, actor}:
            raise ProvenanceError(
                f"{commit}: Actor {commit_actor!r} does not match actor:{actor} integration"
            )


def _role_from_labels(labels: Any) -> str:
    if not isinstance(labels, list) or any(not isinstance(label, dict) for label in labels):
        raise ProvenanceError("pull_request.labels must be a list of objects")
    names = [label.get("name") for label in labels]
    actor_names = sorted(
        name for name in names if isinstance(name, str) and name.casefold().startswith("actor:")
    )
    unknown = sorted(name for name in actor_names if name not in ACTOR_LABELS)
    if unknown:
        raise ProvenanceError(f"pull request has unsupported actor role label(s): {unknown}")
    roles = actor_names
    if len(roles) != 1:
        raise ProvenanceError(
            "pull request must have exactly one actor role label "
            f"({', '.join(sorted(ACTOR_LABELS))}); found {roles}"
        )
    return roles[0].split(":", 1)[1]


def _verify_pull_request(
    root: Path,
    event: dict[str, Any],
    trusted_through: str,
) -> Verification:
    pull = event.get("pull_request")
    if not isinstance(pull, dict):
        raise ProvenanceError("pull_request event payload is missing pull_request")
    base_record = pull.get("base")
    head_record = pull.get("head")
    if not isinstance(base_record, dict) or not isinstance(head_record, dict):
        raise ProvenanceError("pull_request base/head records are missing")
    if base_record.get("ref") != "main":
        raise ProvenanceError("pull_request.base.ref must be main")
    base = _require_sha(root, base_record.get("sha"), "pull_request.base.sha")
    head = _require_sha(root, head_record.get("sha"), "pull_request.head.sha")
    actor = _role_from_labels(pull.get("labels"))
    head_ref = head_record.get("ref")
    if not isinstance(head_ref, str) or not head_ref:
        raise ProvenanceError("pull_request.head.ref must be a non-empty string")
    agent_ref = head_ref == "editorial/batch" or head_ref.startswith("agent/")
    agent_like_ref = head_ref.casefold() == "editorial/batch" or head_ref.casefold().startswith(
        "agent/"
    )
    if agent_like_ref and not agent_ref:
        raise ProvenanceError(f"agent-scoped head ref must use canonical lowercase: {head_ref!r}")
    if agent_ref != (actor == "agent"):
        raise ProvenanceError(
            f"head ref {head_ref!r} and actor:{actor} do not agree on agent provenance"
        )

    cutline = _require_sha(root, trusted_through, "trusted-through cutline")
    _verify_main_integrations(root, cutline, base)

    changed_paths = _changed_paths(root, base, head)
    control_plane_changes = sorted(
        path
        for path in changed_paths
        if path in TRUSTED_GATE_PATHS or path.startswith(".github/workflows/")
    )
    bootstrap = (
        actor == "agent"
        and base == trusted_through
        and head_ref == BOOTSTRAP_REF
        and frozenset(control_plane_changes) == BOOTSTRAP_CONTROL_PLANE_PATHS
    )
    if control_plane_changes and not bootstrap:
        raise ProvenanceError(
            "the Actions/provenance control plane is frozen until supervisor identity is "
            f"bound to an external trust root; found actor:{actor} changes in "
            f"{control_plane_changes}"
        )

    commits = _commits_not_in(root, base, head)
    _enforce_role(root, commits, actor)
    return Verification("pull_request", len(commits), actor)


def _verify_main_integrations(root: Path, base: str, head: str) -> tuple[int, str | None]:
    if not _is_ancestor(root, base, head):
        raise ProvenanceError(f"protected main range is not a fast-forward: {base}..{head}")
    mainline = _git(
        root,
        "rev-list",
        "--first-parent",
        "--reverse",
        f"{base}..{head}",
    ).stdout.splitlines()
    previous = base
    final_actor: str | None = None
    for merge in mainline:
        parents = _parents(root, merge)
        if len(parents) != 2:
            raise ProvenanceError(
                f"{merge}: protected main integration must have exactly two parents"
            )
        if parents[0] != previous:
            raise ProvenanceError(
                f"{merge}: first-parent chain does not continue from protected main {previous}"
            )
        merge_actor = _inspect_commit(root, merge)
        if merge_actor is None:
            raise ProvenanceError(f"{merge}: protected main merge requires one Actor trailer")
        branch_commits = _commits_not_in(root, parents[0], parents[1])
        _enforce_role(root, branch_commits, merge_actor)
        previous = merge
        final_actor = merge_actor
    if previous != head:
        raise ProvenanceError(f"protected main first-parent chain does not end at {head}")
    return len(_commits_not_in(root, base, head, allow_empty=True)), final_actor


def _event_boolean(event: dict[str, Any], field: str, expected: bool) -> None:
    value = event.get(field)
    if value is not expected:
        raise ProvenanceError(f"push.{field} must be {str(expected).lower()}, found {value!r}")


def _verify_push(
    root: Path,
    event: dict[str, Any],
    github_sha: str,
    trusted_through: str,
) -> Verification:
    if event.get("ref") != "refs/heads/main":
        raise ProvenanceError("push provenance gate only accepts refs/heads/main")
    _event_boolean(event, "deleted", False)
    _event_boolean(event, "forced", False)
    head = _require_sha(root, event.get("after"), "push.after")
    sha = _require_sha(root, github_sha, "GITHUB_SHA")
    if head != sha:
        raise ProvenanceError(f"push.after {head} does not match GITHUB_SHA {sha}")

    before = event.get("before")
    if before == ZERO_SHA:
        _event_boolean(event, "created", True)
    else:
        _event_boolean(event, "created", False)
        delivery_base = _require_sha(root, before, "push.before")
        if delivery_base == head or not _is_first_parent_ancestor(root, delivery_base, head):
            raise ProvenanceError(
                f"push.before is not a strict first-parent ancestor of push.after: "
                f"{delivery_base}..{head}"
            )

    cutline = _require_sha(root, trusted_through, "trusted-through cutline")
    commits, actor = _verify_main_integrations(root, cutline, head)
    return Verification("push", commits, actor)


def _dispatch_branch(ref: Any) -> str:
    if not isinstance(ref, str) or not ref:
        raise ProvenanceError("workflow_dispatch.ref must be a non-empty string")
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    if ref.startswith("refs/"):
        raise ProvenanceError(f"workflow_dispatch only accepts branch refs, found {ref!r}")
    return ref


def _origin_main(root: Path) -> str:
    result = _git(root, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}", check=False)
    value = result.stdout.strip()
    if result.returncode != 0 or not SHA_RE.fullmatch(value):
        raise ProvenanceError("origin/main is unavailable in the checked-out full Git graph")
    return value


def _verify_dispatch(
    root: Path,
    event: dict[str, Any],
    github_sha: str,
    trusted_through: str,
) -> Verification:
    head = _require_sha(root, github_sha, "GITHUB_SHA")
    ref = _dispatch_branch(event.get("ref"))
    main = _origin_main(root)
    cutline = _require_sha(root, trusted_through, "trusted-through cutline")
    if not _is_ancestor(root, cutline, main) or not _is_ancestor(root, cutline, head):
        raise ProvenanceError(
            "workflow dispatch ref does not descend from the trusted-through cutline"
        )

    if ref == "main":
        if head != main:
            raise ProvenanceError(f"main dispatch SHA {head} does not match origin/main {main}")
        commits, actor = _verify_main_integrations(root, cutline, head)
        return Verification("workflow_dispatch", commits, actor)
    if ref != "editorial/batch" and not ref.startswith("agent/"):
        raise ProvenanceError(f"unsupported workflow_dispatch branch: {ref!r}")

    _verify_main_integrations(root, cutline, main)
    inputs = event.get("inputs")
    if not isinstance(inputs, dict):
        raise ProvenanceError("agent workflow_dispatch requires an inputs object")
    trusted_main = _require_sha(
        root,
        inputs.get("trusted_main"),
        "workflow_dispatch.inputs.trusted_main",
    )
    if not _is_first_parent_ancestor(root, trusted_main, main):
        raise ProvenanceError(
            f"dispatch trusted_main is not on origin/main first-parent history: {trusted_main}"
        )
    if not _is_ancestor(root, trusted_main, head):
        raise ProvenanceError(f"dispatch head does not descend from trusted_main {trusted_main}")

    commits = _commits_not_in(root, trusted_main, head)
    _enforce_role(root, commits, "agent")
    return Verification("workflow_dispatch", len(commits), "agent")


def verify_event(
    root: Path,
    event_name: str,
    event: dict[str, Any],
    github_sha: str,
    *,
    trusted_through: str = TRUSTED_THROUGH,
) -> Verification:
    if event_name == "pull_request":
        return _verify_pull_request(root, event, trusted_through)
    if event_name == "push":
        return _verify_push(root, event, github_sha, trusted_through)
    if event_name == "workflow_dispatch":
        return _verify_dispatch(root, event, github_sha, trusted_through)
    raise ProvenanceError(f"unsupported GitHub event: {event_name!r}")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not isinstance(args.event_name, str) or not args.event_name:
        raise ProvenanceError("event name is required (--event-name or GITHUB_EVENT_NAME)")
    if args.event_path is None:
        raise ProvenanceError("event path is required (--event-path or GITHUB_EVENT_PATH)")
    if not isinstance(args.sha, str) or not args.sha:
        raise ProvenanceError("head SHA is required (--sha or GITHUB_SHA)")
    try:
        event = json.loads(args.event_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"cannot read GitHub event payload: {exc}") from exc
    if not isinstance(event, dict):
        raise ProvenanceError("GitHub event payload must be a JSON object")
    result = verify_event(
        args.root.resolve(),
        args.event_name,
        event,
        args.sha,
        trusted_through=TRUSTED_THROUGH,
    )
    actor = f", actor:{result.actor}" if result.actor else ""
    print(f"provenance: {result.commits} commit(s) valid ({result.event}{actor})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProvenanceError as exc:
        print(f"provenance error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
