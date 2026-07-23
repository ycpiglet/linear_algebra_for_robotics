from __future__ import annotations

import ast
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
    text = (WORKFLOWS / "provenance.yml").read_text(encoding="utf-8")

    assert workflow["on"] == {
        "pull_request_target": {
            "branches": ["main"],
            "types": ["opened", "synchronize", "reopened", "labeled", "unlabeled", "edited"],
        },
        "repository_dispatch": {"types": ["trusted-provenance"]},
    }
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
    assert "secrets." not in text
    assert "allow-unsafe-pr-checkout" not in text
    assert "github.event.pull_request.head.ref" not in text

    checkout = steps["Checkout trusted base-side verifier"]
    assert checkout["with"] == {
        "ref": (
            "${{ github.event_name == 'pull_request_target' && "
            "github.event.pull_request.base.sha || github.sha }}"
        ),
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    metadata = steps["Resolve immutable PR metadata"]
    assert metadata["id"] == "metadata"
    assert metadata["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "EVENT_NAME": "${{ github.event_name }}",
        "TARGET_PR": "${{ github.event.number }}",
        "DISPATCH_PR": "${{ github.event.client_payload.pr_number }}",
        "DISPATCH_HEAD": "${{ github.event.client_payload.head_sha }}",
    }
    assert 'if [ "$EVENT_NAME" = "pull_request_target" ]' in metadata["run"]
    assert metadata["run"].count('""|*[!0-9]*) exit 1') == 2
    assert metadata["run"].count('test "$pr_number" -ge 1') == 2
    assert metadata["run"].index('test "$pr_number" -ge 1') < metadata["run"].index(
        'gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}"'
    )
    assert 'gh api "repos/${GITHUB_REPOSITORY}/pulls/${pr_number}"' in metadata["run"]
    assert 'test "$live_head" = "$DISPATCH_HEAD"' in metadata["run"]
    assert 'echo "event_path=$event_path"' in metadata["run"]
    assert '} >> "$GITHUB_OUTPUT"' in metadata["run"]
    fetch = steps["Fetch untrusted PR head as Git data only"]
    assert fetch["id"] == "target"
    assert fetch["env"] == {
        "PR_NUMBER": "${{ steps.metadata.outputs.number }}",
        "EXPECTED_BASE": "${{ steps.metadata.outputs.base_sha }}",
        "EXPECTED_HEAD": "${{ steps.metadata.outputs.head_sha }}",
    }
    assert "+refs/pull/${PR_NUMBER}/head:refs/provenance/pr-head" in fetch["run"]
    assert "+refs/pull/${PR_NUMBER}/merge:refs/provenance/pr-merge" in fetch["run"]
    assert 'test "$actual" = "$EXPECTED_HEAD"' in fetch["run"]
    assert 'test "$first_parent" = "$EXPECTED_BASE"' in fetch["run"]
    assert 'test "$second_parent" = "$EXPECTED_HEAD"' in fetch["run"]

    pending = steps["Mark trusted provenance pending on the test merge"]
    report = steps["Verify and report trusted provenance"]
    assert pending["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "TARGET_SHA": "${{ steps.target.outputs.sha }}",
    }
    assert report["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "PROVENANCE_EVENT": "${{ steps.metadata.outputs.event_path }}",
        "TARGET_SHA": "${{ steps.target.outputs.sha }}",
    }
    for step in (pending, report):
        assert "statuses/${TARGET_SHA}" in step["run"]
        assert "context=trusted-provenance" in step["run"]
        assert step.get("continue-on-error") != "true"
    assert "state=pending" in pending["run"]
    assert "python3 -I platform/scripts/verify_provenance.py" in report["run"]
    assert '--event-name pull_request --event-path "$PROVENANCE_EVENT"' in report["run"]
    assert "state=success" in report["run"]
    assert "state=failure" in report["run"]


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


def test_every_workflow_remote_action_is_allowlisted_at_an_exact_commit() -> None:
    paths = workflow_paths()
    assert {path.name for path in paths} == {
        "deploy-pages.yml",
        "editorial-digest.yml",
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


def test_every_uv_runner_command_rejects_stale_lockfiles() -> None:
    runner_path = ROOT / "scripts/dev.py"
    source = runner_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(runner_path))
    uv_calls: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "_run_uv":
            continue
        arguments = [
            argument.value
            for argument in node.args
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        ]
        if arguments and arguments[0] in {"run", "sync"}:
            uv_calls.append(arguments)

    assert uv_calls
    for arguments in uv_calls:
        assert "--locked" in arguments, arguments
    assert '_run_tool("actionlint"' not in source
    assert 'tool_path("actionlint")' in source
    assert '"-shellcheck"' in source
    assert 'tool_path("shellcheck")' in source
    assert 'glob("*.y*ml")' in source


def test_bootstrap_archives_have_reviewed_sha256_pins() -> None:
    manifest = json.loads((ROOT / "scripts/toolchain.json").read_text(encoding="utf-8"))
    reviewed_pins = """
uv linux-x86_64 e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224
uv linux-arm64 03e9fe0a81b0718d0bc84625de3885df6cc3f89a8b6af6121d6b9f6113fb6533
uv macos-x86_64 2ad79983127ffca7d77b77ce6a24278d7e4f7b817a1acf72fea5f8124b4aac5e
uv macos-arm64 33540eb7c883ab857eff79bd5ac2aa31fe27b595abecb4a9c003a2c998447232
uv windows-x86_64 0a23463216d09c6a72ff80ef5dc5a795f07dc1575cb84d24596c2f124a441b7b
quarto linux-x86_64 ea8c897368791ad9f200010c087ea3111b2e556b12a960487dd4e216902aa102
quarto linux-arm64 75fbc5c1121ffe65e564e9d24711db2ad8f617f9552f5dc7d8a06307d72dde38
quarto macos-x86_64 47089a5020cfb41981ba0d4b46e110edfa608722aea45ef248e14efba6d6b18a
quarto macos-arm64 47089a5020cfb41981ba0d4b46e110edfa608722aea45ef248e14efba6d6b18a
quarto windows-x86_64 3dd3b22616dcae65f710b1d6c019b818027312c8cbf54a0a08fdd9842346375e
typst linux-x86_64 59b207df01be2dab9f13e80f73d04d7ff8273ffd46b3dd1b9eef5c60f3eeabea
typst linux-arm64 cdf50ffc7b8ba759ed02200632eda3d78eb8b99aacb6611f4f75684990647620
typst macos-x86_64 30210c7c539c7954db94c063cd98b43fd0a0cad285d656dbbce2a40aee2e79be
typst macos-arm64 fe53838737abf93a774495952a1a797b4686e9c4a21c2d99b9fdf77f46cc3572
typst windows-x86_64 66ae7f0907b4b9afed5c7d6cb9b21e07f0f3c3d4e293ba3e0026a54d88202fe9
actionlint linux-x86_64 8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
actionlint linux-arm64 325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6
actionlint macos-x86_64 5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644
actionlint macos-arm64 aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f
actionlint windows-x86_64 6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9
shellcheck linux-x86_64 8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
shellcheck linux-arm64 12b331c1d2db6b9eb13cfca64306b1b157a86eb69db83023e261eaa7e7c14588
shellcheck macos-x86_64 3c89db4edcab7cf1c27bff178882e0f6f27f7afdf54e859fa041fca10febe4c6
shellcheck macos-arm64 56affdd8de5527894dca6dc3d7e0a99a873b0f004d7aabc30ae407d3f48b0a79
shellcheck windows-x86_64 8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e
node linux-x86_64 55aa7153f9d88f28d765fcdad5ae6945b5c0f98a36881703817e4c450fa76742
node linux-arm64 58c9520501f6ae2b52d5b210444e24b9d0c029a58c5011b797bc1fe7105886f6
node macos-x86_64 dfd0dbd3e721503434df7b7205e719f61b3a3a31b2bcf9729b8b91fea240f080
node macos-arm64 e1a97e14c99c803e96c7339403282ea05a499c32f8d83defe9ef5ec66f979ed1
node windows-x86_64 0ae68406b42d7725661da979b1403ec9926da205c6770827f33aac9d8f26e821
"""
    expected = {
        (tool_name, platform_name): digest
        for tool_name, platform_name, digest in (
            line.split() for line in reviewed_pins.splitlines() if line
        )
    }
    actual = {
        (tool_name, platform_name): asset["sha256"]
        for tool_name, tool in manifest["tools"].items()
        for platform_name, asset in tool["assets"].items()
    }
    assert actual == expected
