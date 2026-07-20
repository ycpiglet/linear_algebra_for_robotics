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


def pull_event(base: str, head: str, labels: list[str], ref: str = "agent/test") -> dict:
    return {
        "pull_request": {
            "base": {"sha": base, "ref": "main"},
            "head": {"sha": head, "ref": ref},
            "labels": [{"name": label} for label in labels],
        }
    }


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


def test_repository_trusted_through_cutline_exists() -> None:
    git(ROOT, "cat-file", "-e", f"{provenance.TRUSTED_THROUGH}^{{commit}}")
    assert git(ROOT, "merge-base", "--is-ancestor", provenance.TRUSTED_THROUGH, "HEAD") == ""


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


def test_agent_pull_request_cannot_replace_the_trusted_control_plane(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/control-plane")
    change_file(root, ".github/workflows/provenance.yml", "name: no-op\n")
    head = commit(root, "Disable trusted check", "agent")

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/control-plane"),
            head,
            trusted_through=base,
        )


def test_pub_016_bootstrap_is_the_only_agent_control_plane_exception(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", provenance.BOOTSTRAP_REF)
    for path in provenance.BOOTSTRAP_CONTROL_PLANE_PATHS:
        change_file(root, path, "# bootstrap\n")
    head = commit(root, "Bootstrap trusted gate", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], provenance.BOOTSTRAP_REF),
        head,
        trusted_through=base,
    )

    assert result == provenance.Verification("pull_request", 1, "agent")


@pytest.mark.parametrize(
    "workflow",
    [
        "permissions:\n  contents: read\n",
        "env: { MODE: &write write }\njobs:\n  test:\n    permissions: { actions: *write }\n",
        "jobs:\n  spoof:\n    name: trusted-provenance\n",
    ],
)
def test_agent_workflow_cannot_change_control_plane_even_with_yaml_aliases(
    tmp_path: Path,
    workflow: str,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/spoof")
    change_file(root, ".github/workflows/spoof.yml", workflow)
    head = commit(root, "Add spoof workflow", "agent")

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/spoof"),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize(
    ("actor", "ref"),
    [
        ("agent", "agent/platform-ci"),
        ("editor", "editor/platform-ci"),
        ("supervisor", "supervisor/platform-ci"),
    ],
)
def test_control_plane_is_frozen_until_supervisor_identity_is_bound(
    tmp_path: Path,
    actor: str,
    ref: str,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", ref)
    change_file(
        root,
        ".github/workflows/platform.yml",
        "permissions:\n  contents: read\njobs:\n  test:\n    name: platform-test\n",
    )
    head = commit(root, "Add platform CI", "agent" if actor == "agent" else None)

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, [f"actor:{actor}"], ref),
            head,
            trusted_through=base,
        )


@pytest.mark.parametrize("path", [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"])
def test_codeowners_trust_root_is_frozen_with_the_control_plane(
    tmp_path: Path,
    path: str,
) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/self-approve")
    change_file(root, path, "* @agent-controlled-owner\n")
    head = commit(root, "Claim control-plane ownership", "agent")

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/self-approve"),
            head,
            trusted_through=base,
        )


def test_privileged_editorial_controller_dependencies_are_frozen(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/editorial-controller")
    change_file(root, "platform/scripts/editorial.py", "print('untrusted controller')\n")
    head = commit(root, "Replace privileged editorial controller", "agent")

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/editorial-controller"),
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

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
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
    change_file(root, ".github/workflows/platform.yml", "permissions: { contents: read }\n")
    commit(root, "Add trusted workflow", "agent")
    git(root, "switch", "main")
    base = merge_branch(root, "agent/bootstrap", "agent")

    git(root, "switch", "agent/old")
    head = merge_branch(root, "main", "agent")

    result = provenance.verify_event(
        root,
        "pull_request",
        pull_event(base, head, ["actor:agent"], "agent/old"),
        head,
        trusted_through=cutline,
    )

    assert result == provenance.Verification("pull_request", 2, "agent")


def test_remote_access_workflow_requires_a_separate_supervisor_pr(tmp_path: Path) -> None:
    root, base = repository(tmp_path)
    git(root, "switch", "-c", "agent/add-cross-platform-remote-access")
    change_file(root, "remote-access/bootstrap-windows.ps1", "# bootstrap\n")
    change_file(root, ".github/workflows/remote-access-tests.yml", "jobs: {}\n")
    head = commit(root, "Add remote access platform CI", "agent")

    with pytest.raises(provenance.ProvenanceError, match="external trust root"):
        provenance.verify_event(
            root,
            "pull_request",
            pull_event(base, head, ["actor:agent"], "agent/add-cross-platform-remote-access"),
            head,
            trusted_through=base,
        )


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
