from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "platform" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_provenance as provenance  # noqa: E402


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    git(root, "commit", "--allow-empty", "-m", "Initial human commit")
    return root, git(root, "rev-parse", "HEAD")


def commit(root: Path, subject: str, actor: str | None = None, *, literal: bool = False) -> str:
    message = subject
    if actor is not None:
        separator = r"\n\n" if literal else "\n\n"
        message = f"{message}{separator}Actor: {actor}"
    git(root, "commit", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


def pull_event(
    base: str,
    head: str,
    labels: list[str],
    ref: str | None = None,
    reviews: list[dict] | None = None,
    *,
    base_repo: dict | None = None,
    head_repo: dict | None = None,
    user_login: object = "agent-app[bot]",
) -> dict:
    if ref is None:
        ref = agent_ref(head)
    target_repo = {
        "id": provenance.TARGET_REPOSITORY_ID,
        "full_name": provenance.TARGET_REPOSITORY_FULL_NAME,
    }
    pull = {
        "base": {
            "sha": base,
            "ref": "main",
            "repo": target_repo if base_repo is None else base_repo,
        },
        "head": {
            "sha": head,
            "ref": ref,
            "repo": target_repo if head_repo is None else head_repo,
        },
        "labels": [{"name": label} for label in labels],
        "user": {"login": user_login},
    }
    if reviews is not None:
        pull["reviews"] = reviews
    return {"pull_request": pull}


def agent_ref(head: str) -> str:
    return f"agent/pr-{head}"


def review(login: str, state: str, commit_id: str) -> dict:
    return {"user": {"login": login}, "state": state, "commit_id": commit_id}


def push_event(
    base: str,
    head: str,
    *,
    created: bool = False,
    forced: bool = False,
    deleted: bool = False,
) -> dict:
    return {
        "ref": "refs/heads/main",
        "before": base,
        "after": head,
        "created": created,
        "forced": forced,
        "deleted": deleted,
    }


def set_origin_main(root: Path, commit_sha: str) -> None:
    git(root, "update-ref", "refs/remotes/origin/main", commit_sha)


def merge_branch(root: Path, branch: str, actor: str | None) -> str:
    message = f"Merge {branch}"
    if actor is not None:
        message += f"\n\nActor: {actor}"
    git(root, "merge", "--no-ff", "-m", message, branch)
    return git(root, "rev-parse", "HEAD")


def change_file(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(root, "add", "--", relative)


def install_canonical_codeowners(root: Path, actor: str | None = None) -> str:
    change_file(
        root,
        provenance.CANONICAL_CODEOWNERS_PATH,
        provenance.CANONICAL_CODEOWNERS,
    )
    return commit(root, "Install canonical CODEOWNERS", actor)


def stage_trust_transition(
    root: Path,
    *,
    codeowners: str = provenance.CANONICAL_CODEOWNERS,
    paths: set[str] | None = None,
) -> None:
    for path in paths if paths is not None else provenance.BOOTSTRAP_CHANGED_PATHS:
        change_file(
            root,
            path,
            codeowners
            if path == provenance.CANONICAL_CODEOWNERS_PATH
            else "# trust transition\n",
        )


def test_repository_trusted_through_cutline_exists() -> None:
    git(ROOT, "cat-file", "-e", f"{provenance.TRUSTED_THROUGH}^{{commit}}")
    assert git(ROOT, "merge-base", "--is-ancestor", provenance.TRUSTED_THROUGH, "HEAD") == ""


def test_repository_codeowners_matches_the_strict_canonical_fixture() -> None:
    fixture = (ROOT / provenance.CANONICAL_CODEOWNERS_PATH).read_text(encoding="utf-8")
    expected = (
        "/.github/CODEOWNERS @ycpiglet\n"
        "/.github/workflows/ @ycpiglet\n"
        "/CODEOWNERS @ycpiglet\n"
        "/docs/CODEOWNERS @ycpiglet\n"
        "/platform/scripts/verify_provenance.py @ycpiglet\n"
        "/platform/scripts/editorial.py @ycpiglet\n"
        "/platform/editorial-runtime/ @ycpiglet\n"
        "/platform/schemas/editorial-event.schema.json @ycpiglet\n"
    )

    assert fixture == provenance.CANONICAL_CODEOWNERS == expected
    assert all(line.split()[1:] == ["@ycpiglet"] for line in fixture.splitlines())


def test_trust_transition_branch_and_changed_paths_are_exact() -> None:
    assert provenance.TRUST_TRANSITION_BASE == "1c2268cbf610ecabc60fef38d71808250315e630"
    git(ROOT, "cat-file", "-e", f"{provenance.TRUST_TRANSITION_BASE}^{{commit}}")
    assert git(
        ROOT,
        "merge-base",
        "--is-ancestor",
        provenance.TRUST_TRANSITION_BASE,
        "HEAD",
    ) == ""
    assert provenance.BOOTSTRAP_REF == "agent/pub-017-trust-transition"
    assert provenance.OWNER_APPROVAL_NOTIFY_WORKFLOW == (
        ".github/workflows/owner-approval-notify.yml"
    )
    assert provenance.OWNER_REVIEW_SIGNAL_WORKFLOW == (
        ".github/workflows/owner-review-signal.yml"
    )
    expected_protected = frozenset(
        {
            ".github/CODEOWNERS",
            ".github/workflows/owner-approval-notify.yml",
            ".github/workflows/owner-review-signal.yml",
            ".github/workflows/provenance.yml",
            "platform/scripts/verify_provenance.py",
        }
    )
    expected_changed = frozenset(
        {
            ".github/CODEOWNERS",
            ".github/workflows/owner-approval-notify.yml",
            ".github/workflows/owner-review-signal.yml",
            ".github/workflows/provenance.yml",
            "CLAUDE.md",
            "platform/design/README.md",
            "platform/design/work-items/PUB-017.yml",
            "platform/editorial/README.md",
            "platform/scripts/verify_provenance.py",
            "platform/tests/test_provenance.py",
            "platform/tests/test_workflow_contract.py",
        }
    )
    assert expected_protected == provenance.BOOTSTRAP_PROTECTED_PATHS
    assert expected_changed == provenance.BOOTSTRAP_CHANGED_PATHS


def test_python_isolated_mode_blocks_sibling_standard_library_shadowing(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    verifier = scripts / "verify_provenance.py"
    verifier.write_bytes((SCRIPTS / "verify_provenance.py").read_bytes())
    (scripts / "re.py").write_text("raise RuntimeError('shadowed')\n", encoding="utf-8")

    plain = subprocess.run(
        [sys.executable, str(verifier), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    isolated = subprocess.run(
        [sys.executable, "-I", str(verifier), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert plain.returncode != 0
    assert "shadowed" in plain.stderr
    assert isolated.returncode == 0, isolated.stderr


def test_agent_pull_request_requires_real_actor_trailer_on_every_commit(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    commit(root, "First", "agent")
    head = commit(root, "Second", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"]),
        "not-a-pr-head",
        trusted_through=base,
    )

    assert result == provenance.Verification("pull_request", 2, "agent")


def test_pull_request_rejects_a_non_main_base_ref(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")
    event = pull_event(base, head, ["actor:agent"])
    event["pull_request"]["base"]["ref"] = "release"

    with pytest.raises(provenance.ProvenanceError, match="base.ref must be main"):
        provenance.verify_event(
            root,
            "pull_request",
            event,
            head,
            trusted_through=base,
        )


def test_base_side_cli_can_treat_pull_request_target_payload_as_pull_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(pull_event(base, head, ["actor:agent"])),
        encoding="utf-8",
    )

    monkeypatch.setattr(provenance, "TRUSTED_THROUGH", base)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_provenance.py",
            "--root",
            str(root),
            "--event-name",
            "pull_request",
            "--event-path",
            str(event_path),
            "--sha",
            head,
            "--require-owner-approval",
            "ycpiglet",
            "--require-agent-login",
            "agent-app[bot]",
        ],
    )

    assert provenance.main() == 0
    assert "provenance: 1 commit(s) valid (pull_request, actor:agent)" in capsys.readouterr().out


def test_agent_pull_request_rejects_missing_actor_trailer(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Missing")

    with pytest.raises(provenance.ProvenanceError, match="requires exactly one canonical"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"]),
            head,
            trusted_through=base,
        )


def test_pull_request_uses_payload_range_when_base_advanced(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")
    git(root, "switch", "main")
    git(root, "switch", "-c", "supervisor/concurrent")
    commit(root, "Concurrent human work")
    git(root, "switch", "main")
    base = merge_branch(root, "supervisor/concurrent", "supervisor")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"]),
        cutline,
        trusted_through=cutline,
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


@pytest.mark.parametrize(
    "message",
    [
        r"Broken\n\nActor: agent",
        r"Broken\r\n\r\nActor: agent",
        "Broken\n\nactor: agent",
        "Broken\n\nActor=agent",
        "Broken\n\nActor: robot",
        "Broken\n\nActor: agent\n continued",
        "Broken\n\nActor: agent\nActor: agent",
        "Broken\n\nActor: agent\nActor: supervisor",
        "Broken\n\n---\nActor: agent",
        "Broken\n\nActor: agent\n\nMore body",
    ],
)
def test_noncanonical_actor_markers_fail_closed(tmp_path: Path, message: str) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    git(root, "commit", "--allow-empty", "-m", message)
    head = git(root, "rev-parse", "HEAD")

    with pytest.raises(provenance.ProvenanceError):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"]),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize("labels", [[], ["actor:agent", "actor:supervisor"]])
def test_pull_request_requires_exactly_one_actor_label(
    tmp_path: Path, labels: list[str]
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exactly one actor role label"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, labels),
            head,
            trusted_through=base,
        )


def test_pull_request_rejects_unknown_actor_namespace_label(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")

    with pytest.raises(provenance.ProvenanceError, match="unsupported actor role"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent", "actor:robot"]),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize(
    ("ref", "label"),
    [("agent/test", "actor:supervisor"), ("topic", "actor:agent")],
)
def test_pull_request_branch_and_label_roles_must_agree(
    tmp_path: Path, ref: str, label: str
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", ref)
    head = commit(root, "Role mismatch", "agent" if label == "actor:agent" else None)

    with pytest.raises(provenance.ProvenanceError, match="do not agree"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, [label], ref),
            head,
            trusted_through=base,
        )


def test_agent_like_ref_must_use_canonical_lowercase(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "Agent/test")
    head = commit(root, "Disguised agent branch")

    with pytest.raises(provenance.ProvenanceError, match="canonical lowercase"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:supervisor"], "Agent/test"),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize("case", ["wrong-suffix", "short-sha", "other-head", "legacy"])
def test_steady_agent_pull_request_requires_exact_one_shot_head_ref(
    tmp_path: Path,
    case: str,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/staging")
    head = commit(root, "Agent work", "agent")
    refs = {
        "wrong-suffix": f"{agent_ref(head)}-extra",
        "short-sha": f"agent/pr-{head[:12]}",
        "other-head": f"agent/pr-{'f' * 40}",
        "legacy": "agent/legacy",
    }

    with pytest.raises(provenance.ProvenanceError, match="immutable exact-head ref"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], refs[case]),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize(
    "login",
    ["human", "Agent-App[bot]", "agent-app［bot］", None],
)
def test_trusted_controller_rejects_non_exact_agent_app_author(
    tmp_path: Path,
    login: object,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/staging")
    head = commit(root, "Agent work", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exact authenticated login"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], user_login=login),
            head,
            trusted_through=base,
            require_agent_login="agent-app[bot]",
        )


def test_trusted_controller_accepts_exact_agent_app_author(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/staging")
    head = commit(root, "Agent work", "agent")

    assert provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], user_login="agent-app[bot]"),
        head,
        trusted_through=base,
        require_agent_login="agent-app[bot]",
    ) == provenance.Verification("pull_request", 1, "agent")


@pytest.mark.parametrize(
    "login",
    ["", "Agent-App[bot]", "human", "agent_app[bot]", "agent-[bot]"],
)
def test_required_agent_login_must_be_a_canonical_app_bot_login(
    tmp_path: Path,
    login: str,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/staging")
    head = commit(root, "Agent work", "agent")

    with pytest.raises(provenance.ProvenanceError, match="canonical lowercase GitHub App"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"]),
            head,
            trusted_through=base,
            require_agent_login=login,
        )


@pytest.mark.parametrize("side", ["base", "head"])
@pytest.mark.parametrize(
    "repository_record",
    [
        {"id": 1, "full_name": provenance.TARGET_REPOSITORY_FULL_NAME},
        {"id": provenance.TARGET_REPOSITORY_ID, "full_name": "fork/project"},
        {"id": str(provenance.TARGET_REPOSITORY_ID), "full_name": "fork/project"},
        {},
    ],
)
def test_agent_pull_request_requires_exact_same_target_repository(
    tmp_path: Path,
    side: str,
    repository_record: dict,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/staging")
    head = commit(root, "Agent work", "agent")
    kwargs = {f"{side}_repo": repository_record}

    with pytest.raises(provenance.ProvenanceError, match="exact target repository"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], **kwargs),
            head,
            trusted_through=base,
        )


def test_bootstrap_ref_cannot_be_reused_after_the_transition(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", "agent/bootstrap-reuse")
    change_file(root, "courseware/chapter.qmd", "not the bootstrap\n")
    head = commit(root, "Reuse bootstrap ref", "agent")

    with pytest.raises(provenance.ProvenanceError, match="reserved.*exact trust-transition"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


def test_editorial_batch_is_the_controller_owned_legacy_exception(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", provenance.EDITORIAL_BATCH_REF)
    head = commit(root, "Digest batch", "agent")

    assert provenance.verify_event(
        root,
        "pull_request",
        pull_event(
            base,
            head,
            ["actor:agent"],
            provenance.EDITORIAL_BATCH_REF,
            user_login="github-actions[bot]",
        ),
        head,
        trusted_through=base,
        require_agent_login="agent-app[bot]",
    ) == provenance.Verification("pull_request", 1, "agent")


def test_human_pull_request_may_omit_actor_but_not_claim_another_role(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "supervisor/change")
    without_trailer = commit(root, "Direct human change")
    event = pull_event(base, without_trailer, ["actor:supervisor"], "supervisor/change")
    assert provenance.verify_event(
        root, "pull_request", event, without_trailer, trusted_through=base
    ) == (
        provenance.Verification("pull_request", 1, "supervisor")
    )

    conflicting = commit(root, "Wrong role", "editor")
    with pytest.raises(provenance.ProvenanceError, match="does not match"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, conflicting, ["actor:supervisor"], "supervisor/change"),
            conflicting,
            trusted_through=base,
        )


@pytest.mark.parametrize("actor", ["editor", "supervisor"])
def test_non_protected_human_role_pull_request_may_come_from_a_fork(
    tmp_path: Path,
    actor: str,
) -> None:
    root, base = repository(tmp_path)
    ref = f"{actor}/fork-change"
    git(root, "switch", "-c", ref)
    head = commit(root, "Human fork change")
    fork = {"id": 987654321, "full_name": "contributor/project"}

    assert provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, [f"actor:{actor}"], ref, head_repo=fork),
        head,
        trusted_through=base,
    ) == provenance.Verification("pull_request", 1, actor)


@pytest.mark.parametrize(
    "path",
    [
        ".github/CODEOWNERS",
        ".github/workflows/provenance.yml",
        ".github/workflows/nested/spoof.yml",
        "CODEOWNERS",
        "docs/CODEOWNERS",
        "platform/editorial-runtime/pyproject.toml",
        "platform/editorial-runtime/nested/config.json",
        "platform/scripts/verify_provenance.py",
        "platform/scripts/editorial.py",
        "platform/schemas/editorial-event.schema.json",
    ],
)
def test_protected_path_classifier_covers_codeowner_contract(path: str) -> None:
    assert provenance.classify_protected_paths({"courseware/chapter.qmd", path}) == (path,)


@pytest.mark.parametrize(
    "path",
    [
        ".github/dependabot.yml",
        ".github/CODEOWNERS.bak",
        ".github/workflows-spoof/job.yml",
        "docs/nested/CODEOWNERS",
        "platform/editorial-runtime-old/pyproject.toml",
        "platform/scripts/verify_provenance.py.bak",
    ],
)
def test_protected_path_classifier_respects_prefix_boundaries(path: str) -> None:
    assert provenance.classify_protected_paths({path}) == ()


def test_ordinary_change_remains_valid_before_codeowners_transition(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/content")
    change_file(root, "courseware/chapter.qmd", "ordinary change\n")
    head = commit(root, "Update ordinary content", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], agent_ref(head)),
        head,
        trusted_through=base,
        require_owner_approval="ycpiglet",
        require_agent_login="agent-app[bot]",
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


def test_pub_017_transition_installs_the_only_pre_trust_protected_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    stage_trust_transition(root)
    head = commit(root, "Install protected trust root", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
        head,
        trusted_through=base,
        require_owner_approval="ycpiglet",
        require_agent_login="agent-app[bot]",
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


def test_pub_017_transition_head_must_be_a_direct_child_of_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    git(root, "switch", "--orphan", provenance.BOOTSTRAP_REF)
    stage_trust_transition(root)
    head = commit(root, "Attempt unrelated root transition", "agent")
    assert git(root, "rev-list", "--parents", "-n", "1", head) == head

    with pytest.raises(provenance.ProvenanceError, match="exact.*bootstrap"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


def test_pub_017_transition_rejects_a_stale_base_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", "f" * 40)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    stage_trust_transition(root)
    head = commit(root, "Attempt transition from stale base", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exact.*bootstrap"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-branch",
        "missing-notify-workflow",
        "missing-review-signal-workflow",
        "missing-provenance-workflow",
        "missing-ordinary-path",
        "extra-protected-path",
        "extra-ordinary-path",
        "multiple-commits",
    ],
)
def test_pre_trust_bootstrap_requires_exact_branch_and_changed_path_set(
    tmp_path: Path,
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    ref = "agent/not-the-transition" if mutation == "wrong-branch" else provenance.BOOTSTRAP_REF
    git(root, "switch", "-c", ref)
    if mutation == "multiple-commits":
        commit(root, "First transition commit", "agent")
    paths = set(provenance.BOOTSTRAP_CHANGED_PATHS)
    if mutation == "missing-notify-workflow":
        paths.remove(provenance.OWNER_APPROVAL_NOTIFY_WORKFLOW)
    if mutation == "missing-review-signal-workflow":
        paths.remove(provenance.OWNER_REVIEW_SIGNAL_WORKFLOW)
    if mutation == "missing-provenance-workflow":
        paths.remove(provenance.PROVENANCE_WORKFLOW)
    if mutation == "missing-ordinary-path":
        paths.remove("CLAUDE.md")
    if mutation == "extra-protected-path":
        paths.add(".github/workflows/extra.yml")
    if mutation == "extra-ordinary-path":
        paths.add("courseware/unreviewed.qmd")
    stage_trust_transition(root, paths=paths)
    head = commit(root, "Attempt trust transition", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exact.*bootstrap"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], ref),
            head,
            trusted_through=base,
        )


def test_pre_trust_bootstrap_requires_exact_codeowners_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    stage_trust_transition(
        root,
        codeowners=provenance.CANONICAL_CODEOWNERS + "* @agent-controlled-owner\n",
    )
    head = commit(root, "Attempt self-owned trust transition", "agent")

    with pytest.raises(provenance.ProvenanceError, match="canonical @ycpiglet fixture"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


def test_malformed_base_codeowners_is_not_a_trust_root(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    change_file(root, provenance.CANONICAL_CODEOWNERS_PATH, "* @agent-controlled-owner\n")
    base = commit(root, "Install malformed CODEOWNERS")
    git(root, "switch", "-c", "agent/workflow")
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Change protected workflow", "agent")

    with pytest.raises(provenance.ProvenanceError, match="does not match.*canonical"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/workflow"),
            head,
            trusted_through=base,
        )


def test_executable_codeowners_is_not_the_canonical_regular_file(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    change_file(
        root,
        provenance.CANONICAL_CODEOWNERS_PATH,
        provenance.CANONICAL_CODEOWNERS,
    )
    git(root, "update-index", "--chmod=+x", provenance.CANONICAL_CODEOWNERS_PATH)
    base = commit(root, "Install executable CODEOWNERS")
    git(root, "switch", "-c", "agent/workflow")
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Change protected workflow", "agent")

    with pytest.raises(provenance.ProvenanceError, match="non-executable regular Git file"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/workflow"),
            head,
            trusted_through=base,
        )


def test_canonical_base_allows_immutable_agent_protected_change(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", "agent/platform-ci")
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Change protected workflow", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], agent_ref(head)),
        head,
        trusted_through=base,
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


@pytest.mark.parametrize("actor", ["editor", "supervisor"])
@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/platform.yml",
        "platform/scripts/verify_provenance.py",
        ".github/CODEOWNERS",
    ],
)
def test_human_roles_cannot_change_protected_paths(
    tmp_path: Path,
    actor: str,
    path: str,
) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    ref = f"{actor}/protected"
    git(root, "switch", "-c", ref)
    change_file(root, path, "human protected change\n")
    head = commit(root, "Attempt human protected change")

    with pytest.raises(provenance.ProvenanceError, match="actor:agent immutable PR"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, [f"actor:{actor}"], ref),
            head,
            trusted_through=base,
        )


def test_editorial_batch_cannot_change_protected_paths(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", provenance.EDITORIAL_BATCH_REF)
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Attempt protected digest batch", "agent")

    with pytest.raises(provenance.ProvenanceError, match="limited to non-protected"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(
                base,
                head,
                ["actor:agent"],
                provenance.EDITORIAL_BATCH_REF,
                user_login="github-actions[bot]",
            ),
            head,
            trusted_through=base,
            require_agent_login="agent-app[bot]",
        )


@pytest.mark.parametrize("actor", ["agent", "supervisor"])
def test_protected_fork_change_is_rejected_for_every_role(
    tmp_path: Path,
    actor: str,
) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    ref = "agent/staging" if actor == "agent" else "supervisor/fork"
    git(root, "switch", "-c", ref)
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Attempt protected fork change", "agent" if actor == "agent" else None)
    event_ref = agent_ref(head) if actor == "agent" else ref
    fork = {"id": 987654321, "full_name": "contributor/project"}

    with pytest.raises(provenance.ProvenanceError):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, [f"actor:{actor}"], event_ref, head_repo=fork),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "wrong-commit",
        "wrong-reviewer",
        "wrong-login-case",
        "dismissed",
        "changes-requested",
    ],
)
def test_trusted_controller_rejects_non_exact_owner_approval(
    tmp_path: Path,
    case: str,
) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", "agent/protected")
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Change protected workflow", "agent")
    reviews = {
        "missing": None,
        "wrong-commit": [review("ycpiglet", "APPROVED", base)],
        "wrong-reviewer": [review("allimbot", "APPROVED", head)],
        "wrong-login-case": [review("Ycpiglet", "APPROVED", head)],
        "dismissed": [
            review("ycpiglet", "APPROVED", head),
            review("ycpiglet", "DISMISSED", head),
        ],
        "changes-requested": [
            review("ycpiglet", "APPROVED", head),
            review("ycpiglet", "CHANGES_REQUESTED", head),
        ],
    }[case]

    with pytest.raises(provenance.ProvenanceError, match="reviews list|exact head"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(
                base,
                head,
                ["actor:agent"],
                agent_ref(head),
                reviews,
            ),
            head,
            trusted_through=base,
            require_owner_approval="ycpiglet",
            require_agent_login="agent-app[bot]",
        )


def test_trusted_controller_accepts_latest_exact_owner_approval(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", "agent/protected")
    change_file(root, ".github/workflows/platform.yml", "jobs: {}\n")
    head = commit(root, "Change protected workflow", "agent")
    reviews = [
        review("ycpiglet", "DISMISSED", base),
        review("allimbot", "APPROVED", head),
        review("ycpiglet", "APPROVED", head),
        review("ycpiglet", "COMMENTED", head),
    ]

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], agent_ref(head), reviews),
        head,
        trusted_through=base,
        require_owner_approval="ycpiglet",
        require_agent_login="agent-app[bot]",
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


def test_owner_approval_flag_is_rejected_for_non_pull_request_events(tmp_path: Path) -> None:
    root, head = repository(tmp_path)

    with pytest.raises(provenance.ProvenanceError, match="only be required for pull_request"):
        provenance.verify_event(
            root,
            "push",
            {},
            head,
            trusted_through=head,
            require_owner_approval="ycpiglet",
        )

    with pytest.raises(provenance.ProvenanceError, match="only be required for pull_request"):
        provenance.verify_event(
            root,
            "push",
            {},
            head,
            trusted_through=head,
            require_agent_login="agent-app[bot]",
        )


def test_delete_of_canonical_codeowners_is_still_classified_as_protected(
    tmp_path: Path,
) -> None:
    root, _ = repository(tmp_path)
    base = install_canonical_codeowners(root)
    git(root, "switch", "-c", "agent/delete-codeowners")
    git(root, "rm", "--", provenance.CANONICAL_CODEOWNERS_PATH)
    head = commit(root, "Delete canonical CODEOWNERS", "agent")

    changed = provenance._changed_paths(root, base, head)
    assert provenance.classify_protected_paths(changed) == (
        provenance.CANONICAL_CODEOWNERS_PATH,
    )
    assert provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], agent_ref(head)),
        head,
        trusted_through=base,
    ) == provenance.Verification("pull_request", 1, "agent")


@pytest.mark.parametrize("path", ["CODEOWNERS", "docs/CODEOWNERS"])
def test_alternate_codeowners_cannot_bootstrap_its_own_owner(
    tmp_path: Path,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = repository(tmp_path)
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    stage_trust_transition(root)
    change_file(root, path, "* @agent-controlled-owner\n")
    head = commit(root, "Add alternate self-owned CODEOWNERS", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exact.*bootstrap"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize("path", provenance.ALTERNATE_CODEOWNERS_PATHS)
def test_alternate_base_codeowners_cannot_impersonate_the_canonical_trust_root(
    tmp_path: Path,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _ = repository(tmp_path)
    change_file(root, path, "* @agent-controlled-owner\n")
    base = commit(root, "Install alternate self-owned CODEOWNERS")
    monkeypatch.setattr(provenance, "TRUST_TRANSITION_BASE", base)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    stage_trust_transition(root)
    head = commit(root, "Attempt transition over alternate CODEOWNERS", "agent")

    with pytest.raises(provenance.ProvenanceError, match="cannot substitute"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
            head,
            trusted_through=base,
        )


def test_workflow_prefix_is_protected_before_the_trust_transition(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/remote-access")
    change_file(root, ".github/workflows/nested/remote-access.yml", "jobs: {}\n")
    head = commit(root, "Add nested protected workflow", "agent")

    with pytest.raises(provenance.ProvenanceError, match="canonical base CODEOWNERS"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/remote-access"),
            head,
            trusted_through=base,
        )


def test_multiple_merge_bases_cannot_hide_a_control_plane_tree_change(tmp_path: Path) -> None:
    root, _ = repository(tmp_path)
    change_file(root, ".github/workflows/platform.yml", "permissions: { contents: read }\n")
    git(root, "commit", "-m", "Seed read-only workflow")
    common = git(root, "rev-parse", "HEAD")

    git(root, "switch", "-c", "side-a")
    change_file(root, ".github/workflows/platform.yml", "permissions: write-all\n")
    a1 = commit(root, "Make side A privileged", "agent")

    git(root, "switch", "-c", "agent/criss-cross", common)
    change_file(root, "side-b.txt", "B\n")
    commit(root, "Create side B", "agent")

    git(root, "switch", "side-a")
    git(root, "merge", "--no-ff", "--no-commit", "agent/criss-cross")
    change_file(root, ".github/workflows/platform.yml", "permissions: { contents: read }\n")
    git(root, "commit", "-m", "Merge B into A\n\nActor: agent")
    base = git(root, "rev-parse", "HEAD")

    git(root, "switch", "agent/criss-cross")
    git(root, "merge", "--no-ff", "-m", "Merge A into B\n\nActor: agent", a1)
    head = git(root, "rev-parse", "HEAD")

    assert len(git(root, "merge-base", "--all", base, head).splitlines()) == 2
    legacy_three_dot = git(root, "diff", "--name-only", f"{base}...{head}").splitlines()
    assert ".github/workflows/platform.yml" not in legacy_three_dot

    assert provenance.classify_protected_paths(provenance._changed_paths(root, base, head)) == (
        ".github/workflows/platform.yml",
    )
    with pytest.raises(provenance.ProvenanceError, match="canonical base CODEOWNERS"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/criss-cross"),
            head,
            trusted_through=base,
        )


def test_latest_main_sync_does_not_attribute_trusted_workflows_to_agent(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/old", cutline)
    change_file(root, "old-topic.txt", "agent topic\n")
    commit(root, "Start old agent topic", "agent")

    git(root, "switch", "-c", "agent/bootstrap", cutline)
    change_file(
        root,
        provenance.CANONICAL_CODEOWNERS_PATH,
        provenance.CANONICAL_CODEOWNERS,
    )
    change_file(root, ".github/workflows/platform.yml", "permissions: { contents: read }\n")
    commit(root, "Add trusted workflow", "agent")
    git(root, "switch", "main")
    base = merge_branch(root, "agent/bootstrap", "agent")

    git(root, "switch", "agent/old")
    head = merge_branch(root, "main", "agent")

    changed = provenance._changed_paths(root, base, head)
    assert changed == {"old-topic.txt"}
    assert provenance.classify_protected_paths(changed) == ()

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], agent_ref(head)),
        head,
        trusted_through=cutline,
    )

    assert result == provenance.Verification("pull_request", 2, "agent")
def test_pull_request_does_not_treat_an_unhealthy_main_base_as_trusted(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/bad")
    commit(root, "Valid branch commit", "agent")
    git(root, "switch", "main")
    base = merge_branch(root, "agent/bad", None)
    git(root, "switch", "-c", "agent/next")
    head = commit(root, "Next valid change", "agent")

    with pytest.raises(provenance.ProvenanceError, match="merge requires one Actor"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/next"),
            head,
            trusted_through=cutline,
        )


def test_protected_main_push_validates_agent_merge_and_branch(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    commit(root, "Agent change", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/test", "agent")

    result = provenance.verify_event(
        root, "push", push_event(base, head), head, trusted_through=base
    )

    assert result == provenance.Verification("push", 2, "agent")


def test_protected_main_push_allows_human_branch_author_identity(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "supervisor/test")
    commit(root, "Human-authored branch commit")
    git(root, "switch", "main")
    head = merge_branch(root, "supervisor/test", "supervisor")

    result = provenance.verify_event(
        root, "push", push_event(base, head), head, trusted_through=base
    )

    assert result == provenance.Verification("push", 2, "supervisor")


def test_main_merge_role_must_match_any_branch_trailer(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    commit(root, "Agent-authored branch commit", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/test", "supervisor")

    with pytest.raises(provenance.ProvenanceError, match="does not match"):
        provenance.verify_event(
            root, "push", push_event(base, head), head, trusted_through=base
        )


def test_protected_main_push_checks_every_integration_in_one_delivery(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/first")
    commit(root, "First branch", "agent")
    git(root, "switch", "main")
    merge_branch(root, "agent/first", None)
    git(root, "switch", "-c", "agent/second")
    commit(root, "Second branch", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/second", "agent")

    with pytest.raises(provenance.ProvenanceError, match="merge requires one Actor"):
        provenance.verify_event(
            root, "push", push_event(base, head), head, trusted_through=base
        )


def test_failed_main_merge_remains_blocked_on_the_next_delivery(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/first")
    commit(root, "First branch", "agent")
    git(root, "switch", "main")
    bad = merge_branch(root, "agent/first", None)
    git(root, "switch", "-c", "agent/second")
    commit(root, "Second branch", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/second", "agent")

    with pytest.raises(provenance.ProvenanceError, match="merge requires one Actor"):
        provenance.verify_event(
            root, "push", push_event(bad, head), head, trusted_through=cutline
        )


def test_protected_main_push_rejects_direct_commit(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    head = commit(root, "Direct push", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exactly two parents"):
        provenance.verify_event(
            root, "push", push_event(base, head), head, trusted_through=base
        )


def test_direct_main_commit_cannot_be_hidden_by_a_later_valid_merge(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    direct = commit(root, "Direct push", "agent")
    git(root, "switch", "-c", "agent/dummy")
    commit(root, "Dummy branch", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/dummy", "agent")

    with pytest.raises(provenance.ProvenanceError, match="exactly two parents"):
        provenance.verify_event(
            root, "push", push_event(direct, head), head, trusted_through=cutline
        )


def test_protected_main_push_rejects_octopus_merge(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/one")
    change_file(root, "one.txt", "one\n")
    commit(root, "First branch", "agent")
    git(root, "switch", "main")
    git(root, "switch", "-c", "agent/two")
    change_file(root, "two.txt", "two\n")
    commit(root, "Second branch", "agent")
    git(root, "switch", "main")
    git(
        root,
        "merge",
        "--no-ff",
        "-m",
        "Octopus merge\n\nActor: agent",
        "agent/one",
        "agent/two",
    )
    head = git(root, "rev-parse", "HEAD")

    with pytest.raises(provenance.ProvenanceError, match="exactly two parents"):
        provenance.verify_event(
            root, "push", push_event(base, head), head, trusted_through=base
        )


def test_protected_main_push_rejects_first_parent_discontinuity(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    branch = commit(root, "Agent branch", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/test", "agent")

    with pytest.raises(provenance.ProvenanceError, match="first-parent"):
        provenance.verify_event(
            root, "push", push_event(branch, head), head, trusted_through=cutline
        )


@pytest.mark.parametrize("field", ["forced", "deleted"])
def test_protected_main_push_rejects_unsafe_delivery_flags(tmp_path: Path, field: str) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    commit(root, "Agent change", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/test", "agent")
    options = {field: True}

    with pytest.raises(provenance.ProvenanceError, match=field):
        provenance.verify_event(
            root,
            "push",
            push_event(base, head, **options),
            head,
            trusted_through=base,
        )


def test_created_main_uses_only_the_trusted_cutline_as_fallback(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/test")
    commit(root, "Agent change", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/test", "agent")
    event = push_event(provenance.ZERO_SHA, head, created=True)

    result = provenance.verify_event(
        root, "push", event, head, trusted_through=cutline
    )
    assert result == provenance.Verification("push", 2, "agent")

    with pytest.raises(provenance.ProvenanceError, match="created"):
        provenance.verify_event(
            root,
            "push",
            push_event(provenance.ZERO_SHA, head),
            head,
            trusted_through=cutline,
        )


def test_agent_dispatch_checks_the_whole_branch_range(tmp_path: Path) -> None:
    root, main = repository(tmp_path)
    set_origin_main(root, main)
    git(root, "switch", "-c", "editorial/batch")
    commit(root, "Missing trailer")
    head = commit(root, "Valid-looking head", "agent")

    with pytest.raises(provenance.ProvenanceError, match="requires exactly one canonical"):
        provenance.verify_event(
            root,
            "workflow_dispatch",
            {"ref": "editorial/batch", "inputs": {"trusted_main": main}},
            head,
            trusted_through=main,
        )


def test_agent_dispatch_accepts_valid_agent_range(tmp_path: Path) -> None:
    root, main = repository(tmp_path)
    set_origin_main(root, main)
    git(root, "switch", "-c", "agent/test")
    commit(root, "First", "agent")
    head = commit(root, "Second", "agent")

    result = provenance.verify_event(
        root,
        "workflow_dispatch",
        {"ref": "refs/heads/agent/test", "inputs": {"trusted_main": main}},
        head,
        trusted_through=main,
    )

    assert result == provenance.Verification("workflow_dispatch", 2, "agent")


def test_agent_dispatch_cannot_choose_its_own_head_as_trusted_main(tmp_path: Path) -> None:
    root, main = repository(tmp_path)
    set_origin_main(root, main)
    git(root, "switch", "-c", "agent/test")
    head = commit(root, "Agent work", "agent")

    with pytest.raises(provenance.ProvenanceError, match="origin/main first-parent"):
        provenance.verify_event(
            root,
            "workflow_dispatch",
            {"ref": "agent/test", "inputs": {"trusted_main": head}},
            head,
            trusted_through=main,
        )


def test_dispatch_rejects_arbitrary_refs_and_missing_origin_main(tmp_path: Path) -> None:
    root, head = repository(tmp_path)
    with pytest.raises(provenance.ProvenanceError, match="origin/main is unavailable"):
        provenance.verify_event(
            root,
            "workflow_dispatch",
            {"ref": "agent/test"},
            head,
            trusted_through=head,
        )

    set_origin_main(root, head)
    with pytest.raises(provenance.ProvenanceError, match="unsupported workflow_dispatch"):
        provenance.verify_event(
            root,
            "workflow_dispatch",
            {"ref": "supervisor/test"},
            head,
            trusted_through=head,
        )


def test_main_dispatch_revalidates_every_merge_since_cutline(tmp_path: Path) -> None:
    root, cutline = repository(tmp_path)
    git(root, "switch", "-c", "agent/first")
    commit(root, "First", "agent")
    git(root, "switch", "main")
    merge_branch(root, "agent/first", None)
    git(root, "switch", "-c", "agent/second")
    commit(root, "Second", "agent")
    git(root, "switch", "main")
    head = merge_branch(root, "agent/second", "agent")
    set_origin_main(root, head)

    with pytest.raises(provenance.ProvenanceError, match="merge requires one Actor"):
        provenance.verify_event(
            root,
            "workflow_dispatch",
            {"ref": "main"},
            head,
            trusted_through=cutline,
        )
