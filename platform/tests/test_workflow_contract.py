from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

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
        "pull_request": {"branches": ["main"]},
        "workflow_dispatch": "",
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
    assert 'git merge --no-edit "$trusted_main"' in prepare["run"]
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
    assert ensure["run"].count("--base main") == 3

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
        "Dispatch read-only batch quality"
    )
    assert ordered_names.index("Dispatch read-only batch quality") < ordered_names.index(
        "Finalize processed issues after durable push"
    )
    dispatch = steps["Dispatch read-only batch quality"]
    assert 'expected="${{ steps.batch.outputs.head_sha }}"' in dispatch["run"]
    assert "git/ref/heads/editorial/batch" in dispatch["run"]
    assert 'test "$remote" = "$expected"' in dispatch["run"]
    assert "gh workflow run publish-web.yml" in dispatch["run"]
    assert "--ref editorial/batch" in dispatch["run"]
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


def test_every_workflow_remote_action_is_allowlisted_at_an_exact_commit() -> None:
    paths = workflow_paths()
    assert {path.name for path in paths} == {
        "deploy-pages.yml",
        "editorial-digest.yml",
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
    }
    for variable, digest in expected.items():
        assert f'{variable}="{digest}"' in script
        assert f'"${{{variable}}}" "${{archive}}" | sha256sum --check --status' in script
