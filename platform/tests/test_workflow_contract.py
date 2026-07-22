from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"

PINNED_ACTIONS = {
    "actions/checkout": "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",  # v7.0.0
    "actions/cache": "55cc8345863c7cc4c66a329aec7e433d2d1c52a9",  # v6.1.0
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",  # v8.0.1
    "astral-sh/setup-uv": "11f9893b081a58869d3b5fccaea48c9e9e46f990",  # v8.3.2
    "peaceiris/actions-gh-pages": "84c30a85c19949d7eee79c4ff27748b70285e453",  # v4.1.0
}


def workflow_paths() -> list[Path]:
    return sorted({*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")})


def load_workflow(name: str) -> dict[str, Any]:
    return load_workflow_path(WORKFLOWS / name)


def load_workflow_path(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def steps_by_name(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["name"]: step for step in job["steps"] if "name" in step}


def uses_in(workflow: dict[str, Any]) -> list[str]:
    return [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "uses" in step
    ]


def assert_required_step(step: dict[str, Any], command: str) -> None:
    assert step["run"] == command
    assert "if" not in step
    assert step.get("continue-on-error") != "true"


def test_publish_triggers_and_quality_are_an_unconditional_read_only_gate() -> None:
    workflow = load_workflow("publish-web.yml")
    quality = workflow["jobs"]["quality"]
    steps = steps_by_name(quality)

    assert workflow["on"] == {
        "push": {"branches": ["main"]},
        "pull_request": {
            "branches": ["main"],
            "types": ["opened", "synchronize", "reopened", "labeled", "unlabeled", "edited"],
        },
        "workflow_dispatch": {
            "inputs": {
                "trusted_main": {
                    "description": "Exact trusted main SHA for an agent/editorial branch review",
                    "required": "false",
                    "type": "string",
                }
            }
        },
    }
    assert "pull_request_target" not in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": (
            "publish-web-${{ github.event_name }}-${{ github.event_name == 'pull_request' && "
            "format('pr-{0}', github.event.number) || github.ref_name }}"
        ),
        "cancel-in-progress": "true",
    }
    assert quality["name"] == "source-contract"
    assert quality["permissions"] == {"contents": "read"}
    assert "if" not in quality
    assert "secrets." not in json.dumps(quality)

    required_runs = {
        "Verify commit provenance": "python3 -I platform/scripts/verify_provenance.py",
        "Test source contracts": "make test",
        "Lint Python and Actions workflows": "make lint",
        "Verify quality tools left a clean workspace": (
            'test -z "$(git status --porcelain --untracked-files=all)"'
        ),
    }
    for name, command in required_runs.items():
        assert_required_step(steps[name], command)

    checkout = next(
        step
        for step in quality["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"] == {"fetch-depth": "0", "persist-credentials": "false"}
    ordered_names = [step.get("name") for step in quality["steps"]]
    assert quality["steps"].index(checkout) < ordered_names.index("Verify commit provenance")
    assert ordered_names.index("Verify commit provenance") < ordered_names.index(
        "Cache pinned toolchain"
    )


def test_trusted_provenance_executes_only_base_side_code() -> None:
    workflow = load_workflow("provenance.yml")
    job = workflow["jobs"]["provenance"]
    steps = steps_by_name(job)
    ordered_names = [step.get("name") for step in job["steps"]]
    text = (WORKFLOWS / "provenance.yml").read_text(encoding="utf-8")

    assert workflow["on"] == {
        "pull_request_target": {
            "branches": ["main"],
            "types": ["opened", "synchronize", "reopened", "labeled", "unlabeled", "edited"],
        },
        "repository_dispatch": {"types": ["trusted-provenance"]},
        "workflow_run": {
            "workflows": ["owner-review-signal"],
            "types": ["completed"],
        },
    }
    assert "pull_request_review" not in workflow["on"]
    assert workflow["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "statuses": "write",
    }
    assert job["name"] == "trusted-provenance-controller"
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "statuses": "write",
    }
    assert job["timeout-minutes"] == "5"
    assert workflow["concurrency"] == {
        "group": (
            "trusted-provenance-${{ github.event_name == 'pull_request_target' && "
            "format('pr-{0}-target', github.event.number) || "
            "github.event_name == 'repository_dispatch' && "
            "format('pr-{0}-dispatch', github.event.client_payload.pr_number) || "
            "format('review-{0}-{1}-{2}-{3}', github.event.workflow_run.head_sha, "
            "github.event.workflow_run.actor.login, "
            "github.event.workflow_run.triggering_actor.login, "
            "github.event.workflow_run.run_attempt) }}"
        ),
        "cancel-in-progress": "true",
    }
    assert "secrets." not in text
    assert "allow-unsafe-pr-checkout" not in text
    assert "github.event.pull_request.head.ref" not in text
    assert "gh pr review" not in text
    assert "actions/upload-artifact" not in text
    assert "actions/download-artifact" not in text
    assert "actions/cache" not in text

    metadata = steps["Resolve immutable PR hints and live base"]
    assert metadata["id"] == "metadata"
    assert metadata["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "EVENT_NAME": "${{ github.event_name }}",
        "TARGET_PR": "${{ github.event.number }}",
        "DISPATCH_PR": "${{ github.event.client_payload.pr_number }}",
        "DISPATCH_HEAD": "${{ github.event.client_payload.head_sha }}",
        "OWNER_LOGIN": "ycpiglet",
        "SIGNAL_NAME": "owner-review-signal",
        "SIGNAL_PATH": ".github/workflows/owner-review-signal.yml",
        "TARGET_OWNER": "ycpiglet",
        "TARGET_REPOSITORY": "ycpiglet/linear_algebra_for_robotics",
        "TARGET_REPOSITORY_ID": "1300261697",
    }
    metadata_run = metadata["run"]
    assert "set -euo pipefail" in metadata_run
    assert "pull_request_target)" in metadata_run
    assert "repository_dispatch)" in metadata_run
    assert "workflow_run)" in metadata_run
    for contract in (
        '.workflow_run.event == "pull_request_review"',
        '.workflow_run.status == "completed"',
        ".workflow_run.name == $name",
        ".workflow_run.actor.login == $owner",
        ".workflow_run.triggering_actor.login == $owner",
        ".workflow_run.run_attempt == 1",
        ".workflow_run.repository.full_name == $repo",
        ".workflow_run.repository.id == $repo_id",
        'normalized_path=${signal_path%%@*}',
        'test "$normalized_path" = "$SIGNAL_PATH"',
        "expected_head=$(jq -er '.workflow_run.head_sha'",
        "expected_head_ref=$(jq -er '.workflow_run.head_branch'",
        'test "$expected_head_ref" = "agent/pr-${expected_head}"',
        'gh api --method GET --paginate "repos/${TARGET_REPOSITORY}/pulls"',
        '-f "head=${TARGET_OWNER}:${expected_head_ref}"',
        "jq -e 'length == 1'",
    ):
        assert contract in metadata_run
    assert "conclusion" not in metadata_run
    assert "workflow_run.pull_requests" not in metadata_run
    assert 'expected_merge=$(jq -er \'.workflow_run.head_sha\'' not in metadata_run
    assert metadata_run.count('expected_merge=""') == 3
    assert metadata_run.count('""|*[!0-9]*) exit 1') == 1
    assert 'test "$pr_number" -ge 1' in metadata_run
    assert metadata_run.count(
        'gh api "repos/${TARGET_REPOSITORY}/pulls/${pr_number}"'
    ) == 1
    assert 'test "$live_state" = "open"' in metadata_run
    assert 'test "$live_base_ref" = "main"' in metadata_run
    assert 'test "$live_base_repo" = "$TARGET_REPOSITORY"' in metadata_run
    assert 'test "$live_head_repo" = "$TARGET_REPOSITORY"' in metadata_run
    assert 'test "$live_base_repo_id" = "$TARGET_REPOSITORY_ID"' in metadata_run
    assert 'test "$live_head_repo_id" = "$TARGET_REPOSITORY_ID"' in metadata_run
    assert 'if [ "$actor_label" = "actor:agent" ]; then' in metadata_run
    assert 'select(length == 1) | .[0]' in metadata_run
    assert "actor:agent|actor:editor|actor:supervisor" in metadata_run
    assert "git " not in metadata_run
    assert "python" not in metadata_run
    assert "curl" not in metadata_run

    checkout = steps["Checkout exact trusted PR base"]
    assert checkout["with"] == {
        "ref": "${{ steps.metadata.outputs.base_sha }}",
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    confirm = steps["Confirm exact trusted base checkout"]
    assert confirm["env"] == {"EXPECTED_BASE": "${{ steps.metadata.outputs.base_sha }}"}
    assert "git rev-parse --verify 'HEAD^{commit}'" in confirm["run"]

    fetch = steps["Fetch initial untrusted PR tuple as Git data only"]
    assert fetch["id"] == "target"
    assert fetch["env"] == {
        "PR_NUMBER": "${{ steps.metadata.outputs.number }}",
        "EXPECTED_BASE": "${{ steps.metadata.outputs.base_sha }}",
        "EXPECTED_HEAD": "${{ steps.metadata.outputs.head_sha }}",
        "EXPECTED_MERGE": "${{ steps.metadata.outputs.expected_merge }}",
    }
    assert "+refs/pull/${PR_NUMBER}/head:refs/provenance/initial-head" in fetch["run"]
    assert "+refs/pull/${PR_NUMBER}/merge:refs/provenance/initial-merge" in fetch["run"]
    assert "git fetch --atomic --no-tags" in fetch["run"]
    assert "&& tuple_matches" in fetch["run"]
    for fail_closed_guard in (
        'test -z "${extra:-}" || return 1',
        'test "$actual_head" = "$EXPECTED_HEAD" || return 1',
        'test "$first_parent" = "$EXPECTED_BASE" || return 1',
        'test "$second_parent" = "$EXPECTED_HEAD" || return 1',
        'test "$merge_sha" = "$EXPECTED_MERGE" || return 1',
    ):
        assert fail_closed_guard in fetch["run"]
    assert 'if [ -n "$EXPECTED_MERGE" ]; then' in fetch["run"]
    assert fetch["run"].count("|| return 1") == 7
    assert fetch["run"].count("return 0") == 1
    assert 'echo "sha=$merge_sha"' in fetch["run"]

    pending = steps["Mark trusted provenance pending on the test merge"]
    approval = steps["Recheck live PR approval and immutable tuple"]
    report = steps["Verify and report trusted provenance"]
    assert pending["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "TARGET_SHA": "${{ steps.target.outputs.sha }}",
    }
    approval_run = approval["run"]
    assert approval["id"] == "approval"
    assert approval_run.count(
        'gh api "repos/${TARGET_REPOSITORY}/pulls/${PR_NUMBER}"'
    ) == 2
    assert "gh api --paginate" in approval_run
    assert "pulls/${PR_NUMBER}/reviews?per_page=100" in approval_run
    assert "{user: {login: .user.login}, state: .state, commit_id: .commit_id}" in approval_run
    assert 'test "$(projection "$before_path")" = "$(projection "$after_path")"' in approval_run
    assert "+refs/pull/${PR_NUMBER}/head:refs/provenance/recheck-head" in approval_run
    assert "+refs/pull/${PR_NUMBER}/merge:refs/provenance/recheck-merge" in approval_run
    for fail_closed_guard in (
        'test -z "${extra:-}" || return 1',
        'test "$actual_head" = "$EXPECTED_HEAD" || return 1',
        'test "$merge_sha" = "$EXPECTED_MERGE" || return 1',
        'test "$first_parent" = "$EXPECTED_BASE" || return 1',
        'test "$second_parent" = "$EXPECTED_HEAD" || return 1',
    ):
        assert fail_closed_guard in approval_run
    assert approval_run.count("|| return 1") == 7
    assert approval_run.count("return 0") == 1
    assert ".base.repo.full_name == $repo" in approval_run
    assert ".head.repo.full_name == $head_repo" in approval_run
    assert ".head.repo.id == $head_repo_id" in approval_run
    assert '== [$actor_label]' in approval_run
    assert 'user: {login: .user.login}' in approval_run
    assert "reviews: $reviews[0]" in approval_run
    assert 'echo "event_path=$event_path"' in approval_run
    assert report["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "PROVENANCE_EVENT": "${{ steps.approval.outputs.event_path }}",
        "EXPECTED_AGENT_LOGIN": "${{ vars.AGENT_APP_BOT_LOGIN }}",
        "TARGET_BASE": "${{ steps.target.outputs.base_sha }}",
        "TARGET_SHA": "${{ steps.target.outputs.sha }}",
    }
    for step in (pending, report):
        assert "statuses/${TARGET_SHA}" in step["run"]
        assert "context=trusted-provenance" in step["run"]
        assert step.get("continue-on-error") != "true"
    assert "state=pending" in pending["run"]
    assert "python3 -I platform/scripts/verify_provenance.py" in report["run"]
    assert '--event-name pull_request --event-path "$PROVENANCE_EVENT"' in report["run"]
    assert '--sha "$TARGET_SHA"' in report["run"]
    assert "--require-owner-approval ycpiglet" in report["run"]
    assert '--require-agent-login "$EXPECTED_AGENT_LOGIN"' in report["run"]
    assert "state=success" in report["run"]
    assert "state=failure" in report["run"]
    assert text.count("statuses/${TARGET_SHA}") == 2
    assert "statuses/${EXPECTED_HEAD}" not in text
    assert ordered_names.index("Resolve immutable PR hints and live base") < ordered_names.index(
        "Checkout exact trusted PR base"
    )
    assert ordered_names.index("Checkout exact trusted PR base") < ordered_names.index(
        "Fetch initial untrusted PR tuple as Git data only"
    )
    assert ordered_names.index(
        "Fetch initial untrusted PR tuple as Git data only"
    ) < ordered_names.index("Mark trusted provenance pending on the test merge")
    assert ordered_names.index(
        "Mark trusted provenance pending on the test merge"
    ) < ordered_names.index("Recheck live PR approval and immutable tuple")
    assert ordered_names.index(
        "Recheck live PR approval and immutable tuple"
    ) < ordered_names.index("Verify and report trusted provenance")


def test_owner_review_signal_is_an_exact_unprivileged_noop() -> None:
    workflow = load_workflow("owner-review-signal.yml")
    text = (WORKFLOWS / "owner-review-signal.yml").read_text(encoding="utf-8")

    assert workflow == {
        "name": "owner-review-signal",
        "on": {
            "pull_request_review": {
                "types": ["submitted", "dismissed"],
            }
        },
        "permissions": {},
        "jobs": {
            "signal": {
                "name": "owner-review-signal",
                "runs-on": "ubuntu-latest",
                "permissions": {},
                "timeout-minutes": "1",
                "steps": [{"name": "Emit fixed owner-review signal", "run": ":"}],
            }
        },
    }
    for forbidden in (
        "uses:",
        "env:",
        "if:",
        "secrets.",
        "checkout",
        "artifact",
        "cache",
        "gh ",
        "curl",
        "api/",
    ):
        assert forbidden not in text


def run_workflow_run_metadata(
    tmp_path: Path,
    association_count: int,
    *,
    actor_login: str = "ycpiglet",
    triggering_actor_login: str | None = None,
    run_attempt: int = 1,
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    metadata = steps_by_name(load_workflow("provenance.yml")["jobs"]["provenance"])[
        "Resolve immutable PR hints and live base"
    ]
    head = "a" * 40
    base = "b" * 40
    head_ref = f"agent/pr-{head}"
    repository = {"id": 1300261697, "full_name": "ycpiglet/linear_algebra_for_robotics"}
    pull = {
        "number": 17,
        "state": "open",
        "base": {"sha": base, "ref": "main", "repo": repository},
        "head": {"sha": head, "ref": head_ref, "repo": repository},
        "labels": [{"name": "actor:agent"}],
    }
    associations = [pull | {"number": 17 + index} for index in range(association_count)]
    event = {
        "workflow_run": {
            "event": "pull_request_review",
            "status": "completed",
            "conclusion": "cancelled",
            "name": "owner-review-signal",
            "actor": {"login": actor_login},
            "triggering_actor": {"login": triggering_actor_login or actor_login},
            "run_attempt": run_attempt,
            "path": ".github/workflows/owner-review-signal.yml@refs/pull/17/merge",
            "repository": repository,
            "head_sha": head,
            "head_branch": head_ref,
            "pull_requests": [],
        }
    }

    event_path = tmp_path / "workflow-run.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    output_path = tmp_path / "github-output"
    script_path = tmp_path / "metadata.sh"
    script_path.write_text(metadata["run"], encoding="utf-8")
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    gh_path = mock_bin / "gh"
    gh_path.write_text(
        """#!/bin/sh
case "$*" in
  *"--method GET --paginate repos/ycpiglet/linear_algebra_for_robotics/pulls"*)
    printf '%s\n' "$MOCK_ASSOCIATIONS"
    ;;
  *"api repos/ycpiglet/linear_algebra_for_robotics/pulls/17"*)
    printf '%s\n' "$MOCK_LIVE_PR"
    ;;
  *)
    exit 91
    ;;
esac
""",
        encoding="utf-8",
    )
    gh_path.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{mock_bin}:{os.environ['PATH']}",
        "GH_TOKEN": "test-token",
        "EVENT_NAME": "workflow_run",
        "TARGET_PR": "",
        "DISPATCH_PR": "",
        "DISPATCH_HEAD": "",
        "OWNER_LOGIN": "ycpiglet",
        "SIGNAL_NAME": "owner-review-signal",
        "SIGNAL_PATH": ".github/workflows/owner-review-signal.yml",
        "TARGET_OWNER": "ycpiglet",
        "TARGET_REPOSITORY": "ycpiglet/linear_algebra_for_robotics",
        "TARGET_REPOSITORY_ID": "1300261697",
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_OUTPUT": str(output_path),
        "GITHUB_REPOSITORY": "ycpiglet/linear_algebra_for_robotics",
        "RUNNER_TEMP": str(tmp_path),
        "MOCK_ASSOCIATIONS": "\n".join(json.dumps(item) for item in associations),
        "MOCK_LIVE_PR": json.dumps(pull),
    }
    result = subprocess.run(
        ["bash", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    return result, output, head


def test_workflow_run_resolves_realistic_empty_pull_array_by_immutable_ref(
    tmp_path: Path,
) -> None:
    result, output, head = run_workflow_run_metadata(tmp_path, 1)

    assert result.returncode == 0, result.stderr
    assert "number=17\n" in output
    assert f"head_sha={head}\n" in output
    assert f"head_ref=agent/pr-{head}\n" in output
    assert "expected_merge=\n" in output


@pytest.mark.parametrize("association_count", [0, 2])
def test_workflow_run_rejects_zero_or_multiple_immutable_ref_associations(
    tmp_path: Path,
    association_count: int,
) -> None:
    result, output, _ = run_workflow_run_metadata(tmp_path, association_count)

    assert result.returncode != 0
    assert output == ""


@pytest.mark.parametrize(
    "identity",
    [
        {"actor_login": "other-reviewer"},
        {"triggering_actor_login": "other-reviewer"},
        {"run_attempt": 2},
    ],
)
def test_workflow_run_rejects_non_owner_or_rerun_signal_identity(
    tmp_path: Path,
    identity: dict[str, str | int],
) -> None:
    result, output, _ = run_workflow_run_metadata(tmp_path, 1, **identity)

    assert result.returncode != 0
    assert output == ""


def test_publication_build_runs_for_forks_and_dispatch_without_write_credentials() -> None:
    workflow = load_workflow("publish-web.yml")
    build = workflow["jobs"]["build"]
    steps = steps_by_name(build)

    assert set(workflow["jobs"]) == {"quality", "build"}
    assert build["name"] == "publication-build"
    assert build["needs"] == "quality"
    assert build["permissions"] == {"contents": "read"}
    assert "if" not in build
    assert "secrets." not in json.dumps(build)
    assert_required_step(
        steps["Build review site (web+review profiles, Hypothesis enabled)"], "make review"
    )

    assert steps["Upload immutable main Pages artifact"]["if"] == "github.event_name == 'push'"
    assert steps["Upload immutable PR preview artifact"]["if"] == (
        "github.event_name == 'pull_request'"
    )
    assert steps["Upload immutable dispatched review artifact"]["if"] == (
        "github.event_name == 'workflow_dispatch'"
    )
    assemble = steps["Assemble deployment root (reader + /review)"]["run"]
    assert 'printf \'%s\\n\' "${{ github.sha }}" > public/source-commit.txt' in assemble
    assert "contents: write" not in (WORKFLOWS / "publish-web.yml").read_text(encoding="utf-8")


def test_trusted_deploy_rejects_dispatches_and_stale_main_runs() -> None:
    workflow = load_workflow("deploy-pages.yml")
    deploy = workflow["jobs"]["deploy"]
    steps = steps_by_name(deploy)

    assert workflow["on"] == {
        "workflow_run": {"workflows": ["publish-web"], "types": ["completed"]}
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "gh-pages-main",
        "cancel-in-progress": "false",
    }
    assert deploy["name"] == "pages-deploy"
    assert deploy["permissions"] == {"actions": "read", "contents": "write"}
    assert deploy["if"] == (
        "${{ github.event.workflow_run.conclusion == 'success' && "
        "github.event.workflow_run.event == 'push' && "
        "github.event.workflow_run.head_branch == 'main' && "
        "github.event.workflow_run.head_repository.full_name == github.repository }}"
    )

    assert [step["uses"].split("@", 1)[0] for step in deploy["steps"] if "uses" in step] == [
        "actions/download-artifact",
        "peaceiris/actions-gh-pages",
    ]
    download = steps["Download the triggering main build artifact"]
    assert download["with"] == {
        "name": "pages-main-${{ github.event.workflow_run.id }}",
        "path": "deploy",
        "github-token": "${{ secrets.GITHUB_TOKEN }}",
        "repository": "${{ github.repository }}",
        "run-id": "${{ github.event.workflow_run.id }}",
    }

    for name in (
        "Verify triggering commit is current main",
        "Recheck current main before deployment",
    ):
        check = steps[name]
        assert "if" not in check
        assert check.get("continue-on-error") != "true"
        assert 'git/ref/heads/main" --jq .object.sha' in check["run"]
        assert 'test "$current_main" = "${{ github.event.workflow_run.head_sha }}"' in check["run"]

    assert steps["Verify deployment artifact shape"]["run"].splitlines() == [
        "test -s deploy/index.html",
        "test -s deploy/review/index.html",
        'test "$(cat deploy/source-commit.txt)" = "${{ github.event.workflow_run.head_sha }}"',
    ]


def test_editorial_uses_trusted_controller_and_two_phase_finalize() -> None:
    workflow = load_workflow("editorial-digest.yml")
    digest = workflow["jobs"]["digest"]
    steps = steps_by_name(digest)
    ordered_names = [step.get("name") for step in digest["steps"]]
    text = (WORKFLOWS / "editorial-digest.yml").read_text(encoding="utf-8")

    assert workflow["on"] == {
        "schedule": [{"cron": "0 21 * * *"}],
        "repository_dispatch": {"types": ["editorial-digest"]},
    }
    assert "workflow_dispatch" not in workflow["on"]
    assert workflow["permissions"] == {
        "actions": "write",
        "contents": "write",
        "issues": "write",
        "pull-requests": "write",
    }
    assert workflow["concurrency"] == {
        "group": "editorial-digest",
        "cancel-in-progress": "false",
    }
    assert digest["if"] == "${{ vars.EDITORIAL_FREEZE != 'true' }}"
    assert "pip install" not in text
    assert "gh pr review" not in text
    assert "/actions/variables/EDITORIAL_FREEZE" not in text

    slot_guard = steps["Validate editorial batch key slot"]
    assert slot_guard["env"] == {"KEY_SLOT": "${{ vars.EDITORIAL_BATCH_KEY_SLOT }}"}
    assert '""|primary|next' in slot_guard["run"]
    assert "지원하지 않는 EDITORIAL_BATCH_KEY_SLOT" in slot_guard["run"]

    trusted = steps["Checkout trusted controller from main"]
    assert trusted["with"] == {
        "ref": "${{ github.sha }}",
        "path": "controller",
        "persist-credentials": "false",
    }
    batch = steps["Checkout isolated batch workspace"]
    assert batch["with"] == {
        "fetch-depth": "0",
        "ref": "${{ github.sha }}",
        "path": "batch",
        "persist-credentials": "false",
    }
    push_auth = steps["Checkout isolated batch push credential (primary)"]
    assert push_auth["if"] == (
        "steps.precheck.outputs.pending != '0' && vars.EDITORIAL_BATCH_KEY_SLOT != 'next'"
    )
    assert push_auth["with"] == {
        "fetch-depth": "0",
        "ref": "${{ github.sha }}",
        "path": "push-auth",
        "ssh-key": "${{ secrets.EDITORIAL_BATCH_SSH_KEY }}",
        "persist-credentials": "true",
    }
    push_auth_next = steps["Checkout isolated batch push credential (next)"]
    assert push_auth_next["if"] == (
        "steps.precheck.outputs.pending != '0' && vars.EDITORIAL_BATCH_KEY_SLOT == 'next'"
    )
    assert push_auth_next["with"] == {
        "fetch-depth": "0",
        "ref": "${{ github.sha }}",
        "path": "push-auth",
        "ssh-key": "${{ secrets.EDITORIAL_BATCH_SSH_KEY_NEXT }}",
        "persist-credentials": "true",
    }
    assert steps["Install pinned uv"]["with"] == {
        "version": "0.11.28",
        "enable-cache": "false",
        "python-version": "3.12",
    }
    assert steps["Sync locked editorial runtime"]["run"] == (
        "uv sync --project controller/platform/editorial-runtime --locked --no-dev"
    )

    prepare = steps["Prepare batch branch"]
    assert prepare["working-directory"] == "batch"
    assert 'trusted_main="${{ github.sha }}"' in prepare["run"]
    assert 'git merge-base --is-ancestor origin/editorial/batch "$trusted_main"' in prepare["run"]
    assert "Actor: agent" in prepare["run"]
    assert 'git merge -m "$(printf ' in prepare["run"]
    guard = steps["Reject untrusted batch control-plane changes"]
    assert guard["working-directory"] == "batch"
    for protected in (
        ".github/workflows/publish-web.yml",
        "Makefile",
        "scripts/bootstrap-tools.sh",
        "pyproject.toml",
        "uv.lock",
        "platform/scripts/editorial.py",
        "platform/editorial-runtime/uv.lock",
        "platform/tests/test_workflow_contract.py",
    ):
        assert protected in guard["run"]
    assert '"$trusted_main"...HEAD' in guard["run"]
    assert 'awk \'$1 == "120000"' in guard["run"]

    apply_run = steps["Fetch and apply proposals"]["run"]
    apply_only = apply_run.split('"$controller" apply', 1)[1]
    assert '--root "$GITHUB_WORKSPACE/batch"' in apply_only
    assert "--repo" not in apply_only
    assert "> /tmp/editorial-outcomes.json" in apply_only

    push = steps["Push batch branch"]
    assert push["working-directory"] == "batch"
    assert "env" not in push
    assert "expected=$(git rev-parse HEAD)" in push["run"]
    assert 'fetch "$GITHUB_WORKSPACE/batch" HEAD' in push["run"]
    assert 'test "$fetched" = "$expected"' in push["run"]
    assert 'origin "$expected:refs/heads/editorial/batch"' in push["run"]
    assert 'echo "before_sha=$base" >> "$GITHUB_OUTPUT"' in push["run"]
    assert 'echo "pushed=false" >> "$GITHUB_OUTPUT"' in push["run"]
    assert 'echo "pushed=true" >> "$GITHUB_OUTPUT"' in push["run"]
    assert "--force" not in push["run"]
    ensure = steps["Ensure batch PR exists"]
    assert ensure["id"] == "batch-pr"
    assert ensure["run"].count("--base main") == 3
    assert '--label "actor:agent"' in ensure["run"]
    assert "merge commit 본문의 마지막 trailer" in ensure["run"]
    assert 'test "$actor_labels" = "actor:agent"' in ensure["run"]
    assert 'echo "number=$open_pr" >> "$GITHUB_OUTPUT"' in ensure["run"]
    assert "gh pr edit" not in ensure["run"]

    assert ordered_names.index("Fetch and apply proposals") < ordered_names.index(
        "Checkout isolated batch push credential (primary)"
    )
    primary_auth_index = ordered_names.index(
        "Checkout isolated batch push credential (primary)"
    )
    next_auth_index = ordered_names.index("Checkout isolated batch push credential (next)")
    assert primary_auth_index < next_auth_index
    assert next_auth_index < ordered_names.index("Push batch branch")
    assert ordered_names.index("Push batch branch") < ordered_names.index("Ensure batch PR exists")
    assert ordered_names.index("Ensure batch PR exists") < ordered_names.index(
        "Dispatch trusted batch quality and provenance"
    )
    trusted_dispatch_index = ordered_names.index(
        "Dispatch trusted batch quality and provenance"
    )
    assert trusted_dispatch_index < ordered_names.index(
        "Finalize processed issues after durable push"
    )
    dispatch = steps["Dispatch trusted batch quality and provenance"]
    assert 'expected="${{ steps.batch.outputs.head_sha }}"' in dispatch["run"]
    assert "git/ref/heads/editorial/batch" in dispatch["run"]
    assert 'test "$remote" = "$expected"' in dispatch["run"]
    assert "gh workflow run publish-web.yml" in dispatch["run"]
    assert "--ref editorial/batch" in dispatch["run"]
    assert 'trusted_main="${{ github.sha }}"' in dispatch["run"]
    assert '-f "trusted_main=$trusted_main"' in dispatch["run"]
    assert 'pr_number="${{ steps.batch-pr.outputs.number }}"' in dispatch["run"]
    assert "event_type=trusted-provenance" in dispatch["run"]
    assert 'client_payload[pr_number]=$pr_number' in dispatch["run"]
    assert 'client_payload[head_sha]=$expected' in dispatch["run"]
    assert dispatch.get("continue-on-error") != "true"
    finalize = steps["Finalize processed issues after durable push"]
    assert finalize["if"] == "success() && steps.precheck.outputs.pending != '0'"
    assert "controller/platform/scripts/editorial.py finalize" in finalize["run"]
    assert finalize.get("continue-on-error") != "true"

    runbook = (ROOT / "platform/editorial/README.md").read_text(encoding="utf-8")
    assert "queued" in runbook and "in_progress" in runbook and "terminal" in runbook
    for rotation_contract in (
        "blue/green",
        "EDITORIAL_BATCH_SSH_KEY_NEXT",
        "Issue: #<번호>",
        "pushed=true",
        "before_sha != head_sha",
        "read_only=false",
        "last_used",
        "즉시 `true`로 재동결·drain",
        "활성 secret을 직접",
    ):
        assert rotation_contract in runbook
    for rollback_contract in (
        "deploy-key-only ruleset을 비활성화",
        "rollback PR",
        "freeze를 일시",
        "다시 동결·drain",
        "ruleset을 둔 채 workflow만 revert",
    ):
        assert rollback_contract in runbook
    runtime = tomllib.loads(
        (ROOT / "platform/editorial-runtime/pyproject.toml").read_text(encoding="utf-8")
    )
    assert runtime["project"]["dependencies"] == ["jsonschema==4.26.0"]
    lock = (ROOT / "platform/editorial-runtime/uv.lock").read_text(encoding="utf-8")
    assert 'name = "jsonschema"\nversion = "4.26.0"' in lock


def test_owner_approval_notification_is_read_only_and_fail_closed() -> None:
    workflow = load_workflow("owner-approval-notify.yml")
    job = workflow["jobs"]["notify"]
    steps = steps_by_name(job)
    ordered_names = [step["name"] for step in job["steps"]]
    text = (WORKFLOWS / "owner-approval-notify.yml").read_text(encoding="utf-8")

    assert workflow["on"] == {
        "pull_request_target": {
            "branches": ["main"],
            "types": ["opened", "synchronize", "reopened", "ready_for_review"],
        },
        "repository_dispatch": {"types": ["trusted-provenance"]},
    }
    assert workflow["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
    }
    assert workflow["concurrency"] == {
        "group": (
            "owner-approval-notify-${{ github.event.pull_request.number || "
            "github.event.client_payload.pr_number }}-${{ "
            "github.event.pull_request.head.sha || github.event.client_payload.head_sha }}"
        ),
        "cancel-in-progress": "true",
    }
    assert job["name"] == "owner-approval-notify"
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == "5"
    assert uses_in(workflow) == []
    assert "actions/checkout" not in text
    assert "git fetch" not in text
    assert "git checkout" not in text
    assert "make " not in text
    assert "python" not in text
    assert "actor:" not in text.casefold()
    assert "labels" not in text.casefold()

    target = steps["Resolve immutable notification target"]
    inspect = steps["Inspect live protected paths"]
    notify = steps["Notify owner approval channel"]
    assert ordered_names == [
        "Resolve immutable notification target",
        "Inspect live protected paths",
        "Notify owner approval channel",
    ]
    assert target["env"] == {"GH_TOKEN": "${{ github.token }}"}
    assert "$GITHUB_EVENT_PATH" in target["run"]
    assert ".pull_request.head.sha" in target["run"]
    assert ".client_payload.pr_number" in target["run"]
    assert ".client_payload.head_sha" in target["run"]
    assert 'test("^[0-9a-f]{40}$")' in target["run"]
    assert "${{ github.event" not in target["run"]
    assert "${{ github.event" not in inspect["run"]
    assert "${{ github.event" not in notify["run"]

    assert inspect["id"] == "inspect"
    assert inspect["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "PR_NUMBER": "${{ steps.target.outputs.number }}",
        "EXPECTED_HEAD": "${{ steps.target.outputs.expected_head }}",
        "EXPECTED_AGENT_LOGIN": "${{ vars.AGENT_APP_BOT_LOGIN }}",
        "TARGET_REPOSITORY": "ycpiglet/linear_algebra_for_robotics",
        "TARGET_REPOSITORY_ID": "1300261697",
    }
    assert 'test("^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?\\\\[bot\\\\]$")' in inspect[
        "run"
    ]
    assert inspect["run"].count(
        'gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}"'
    ) == 2
    assert 'pulls/${PR_NUMBER}/files?per_page=100' in inspect["run"]
    assert "--paginate --slurp" in inspect["run"]
    assert '.state == "open"' in inspect["run"]
    assert ".draft == false" in inspect["run"]
    assert '.base.ref == "main"' in inspect["run"]
    assert '(.base.sha | test("^[0-9a-f]{40}$"))' in inspect["run"]
    assert ".head.sha == $head" in inspect["run"]
    assert inspect["run"].count(".base.repo.id == $repository_id") == 2
    assert inspect["run"].count(".head.repo.id == $repository_id") == 2
    assert inspect["run"].count(".head.repo.full_name == $repository") == 2
    assert inspect["run"].count(".user.login == $login") == 2
    assert inspect["run"].count('.head.ref == ("agent/pr-" + $head)') == 2
    assert inspect["run"].count(
        '.head.ref == "agent/pub-017-trust-transition"'
    ) == 2
    assert 'expected_base=$(jq -r .base.sha "$live_before")' in inspect["run"]
    assert inspect["run"].count(".base.sha == $base") == 1
    assert ".changed_files == $changed_files" in inspect["run"]
    assert inspect["run"].count('--argjson changed_files "$changed_files"') == 1
    assert inspect["run"].index('changed_files=$(jq -r .changed_files') < inspect["run"].index(
        '--argjson changed_files "$changed_files"'
    ) < inspect["run"].index(".changed_files == $changed_files")
    assert ".previous_filename" in inspect["run"]
    assert '(.previous_filename | type) == "string"' in inspect["run"]
    for protected_path in (
        '.github/CODEOWNERS',
        '.github/workflows/',
        'CODEOWNERS',
        'docs/CODEOWNERS',
        'platform/scripts/verify_provenance.py',
        'platform/scripts/editorial.py',
        'platform/editorial-runtime/',
        'platform/schemas/editorial-event.schema.json',
    ):
        assert protected_path in inspect["run"]
    assert 'startswith(".github/")' not in inspect["run"]
    assert 'then ".github/**"' not in inspect["run"]
    assert "printf 'notify=false" in inspect["run"]
    assert "printf 'notify=true" in inspect["run"]

    assert notify["if"] == "steps.inspect.outputs.notify == 'true'"
    assert notify.get("continue-on-error") != "true"
    assert notify["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "NTFY_TOPIC": "${{ secrets.NTFY_TOPIC }}",
        "PR_NUMBER": "${{ steps.target.outputs.number }}",
        "EXPECTED_BASE": "${{ steps.inspect.outputs.base_sha }}",
        "EXPECTED_HEAD": "${{ steps.target.outputs.expected_head }}",
        "EXPECTED_AGENT_LOGIN": "${{ vars.AGENT_APP_BOT_LOGIN }}",
        "TARGET_REPOSITORY": "ycpiglet/linear_algebra_for_robotics",
        "TARGET_REPOSITORY_ID": "1300261697",
        "HEAD_SHORT": "${{ steps.inspect.outputs.head_short }}",
        "PATH_SUMMARY": "${{ steps.inspect.outputs.summary }}",
    }
    topic_env_steps = [step for step in job["steps"] if "NTFY_TOPIC" in step.get("env", {})]
    assert topic_env_steps == [notify]
    assert text.count("${{ secrets.NTFY_TOPIC }}") == 1
    assert 'topic: env.NTFY_TOPIC' in notify["run"]
    assert 'title: "보호 경로 owner 승인 필요"' in notify["run"]
    assert '"PR #" + env.PR_NUMBER' in notify["run"]
    assert '" | 보호 경로: " + env.PATH_SUMMARY' in notify["run"]
    assert '" | head " + env.HEAD_SHORT' in notify["run"]
    assert '"https://github.com/" + env.GITHUB_REPOSITORY' in notify["run"]
    assert "--data-binary @-" in notify["run"]
    assert "--output /dev/null" in notify["run"]
    for retry_option in (
        "--retry 3",
        "--retry-all-errors",
        "--connect-timeout 5",
        "--max-time 20",
    ):
        assert retry_option in notify["run"]
    assert notify["run"].rstrip().endswith("https://ntfy.sh")
    assert "https://ntfy.sh/" not in notify["run"]
    assert '"$NTFY_TOPIC"' not in notify["run"]
    for final_identity_check in (
        ".base.repo.id == $repository_id",
        ".base.sha == $base",
        ".head.repo.id == $repository_id",
        ".head.repo.full_name == $repository",
        ".user.login == $login",
        '.head.ref == ("agent/pr-" + $head)',
        '.head.ref == "agent/pub-017-trust-transition"',
    ):
        assert final_identity_check in notify["run"]


def test_every_workflow_remote_action_is_allowlisted_at_an_exact_commit() -> None:
    paths = workflow_paths()
    assert {path.name for path in paths} == {
        "deploy-pages.yml",
        "editorial-digest.yml",
        "owner-approval-notify.yml",
        "owner-review-signal.yml",
        "provenance.yml",
        "publish-web.yml",
    }
    seen: set[str] = set()
    for path in paths:
        for action in uses_in(load_workflow_path(path)):
            owner, separator, commit = action.partition("@")
            assert separator == "@", action
            assert owner in PINNED_ACTIONS, action
            assert commit == PINNED_ACTIONS[owner], action
            seen.add(owner)
    assert seen == set(PINNED_ACTIONS)


def test_every_uv_make_command_rejects_stale_lockfiles() -> None:
    lines = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    uv_commands = [line.strip() for line in lines if "$(UV) sync" in line or "$(UV) run" in line]
    assert uv_commands
    for command in uv_commands:
        assert "--locked" in command, command
    workflow_lint = next(line for line in lines if "$(ACTIONLINT)" in line)
    assert '-shellcheck "$(SHELLCHECK)"' in workflow_lint
    assert "*.yml" in workflow_lint and "*.yaml" in workflow_lint


def test_bootstrap_archives_have_reviewed_sha256_pins() -> None:
    script = (ROOT / "scripts/bootstrap-tools.sh").read_text(encoding="utf-8")
    expected = {
        "QUARTO_SHA256": "ea8c897368791ad9f200010c087ea3111b2e556b12a960487dd4e216902aa102",
        "TYPST_SHA256": "59b207df01be2dab9f13e80f73d04d7ff8273ffd46b3dd1b9eef5c60f3eeabea",
        "UV_SHA256": "e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224",
        "ACTIONLINT_SHA256": (
            "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
        ),
        "SHELLCHECK_SHA256": (
            "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198"
        ),
    }
    for variable, digest in expected.items():
        assert f'{variable}="{digest}"' in script
        assert f'"${{{variable}}}" "${{archive}}" | sha256sum --check --status' in script
