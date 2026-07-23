from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import stat
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/dev.py"
MANIFEST_PATH = ROOT / "scripts/toolchain.json"


def load_runner():
    specification = importlib.util.spec_from_file_location("atlas_dev_runner", RUNNER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_platform_aliases_are_normalized_and_unknown_platforms_fail_closed() -> None:
    runner = load_runner()

    assert runner.platform_key("Linux", "AMD64") == "linux-x86_64"
    assert runner.platform_key("Linux", "aarch64") == "linux-arm64"
    assert runner.platform_key("Darwin", "x86_64") == "macos-x86_64"
    assert runner.platform_key("Darwin", "arm64") == "macos-arm64"
    assert runner.platform_key("Windows", "AMD64") == "windows-x86_64"
    with pytest.raises(runner.DevError, match="Unsupported development platform"):
        runner.platform_key("Plan9", "mips")


def test_pinned_manifest_covers_the_supported_os_and_cpu_matrix() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    supported = {
        "linux-x86_64",
        "linux-arm64",
        "macos-x86_64",
        "macos-arm64",
        "windows-x86_64",
    }

    assert manifest["schema_version"] == 1
    assert manifest["python_version"] == "3.12.13"
    assert set(manifest["tools"]) == {
        "uv",
        "quarto",
        "typst",
        "actionlint",
        "shellcheck",
        "node",
    }
    for name, tool in manifest["tools"].items():
        assert set(tool["assets"]) == supported, name
        for platform_name, asset in tool["assets"].items():
            assert asset["url"].startswith("https://"), (name, platform_name)
            assert re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]), (name, platform_name)
            assert "\\" not in asset["executable"], (name, platform_name)
            if platform_name.startswith("windows-"):
                assert asset["executable"].endswith(".exe"), (name, platform_name)
            else:
                assert not asset["executable"].endswith((".exe", ".cmd")), (
                    name,
                    platform_name,
                )


def test_common_task_graph_preserves_the_existing_developer_contract() -> None:
    runner = load_runner()

    assert set(runner.TASKS) == {
        "bootstrap",
        "sync",
        "artifact-audit",
        "validate",
        "test",
        "workflow-lint",
        "lint",
        "web",
        "review",
        "book",
        "proof",
        "all",
        "preview",
        "clean",
        "doctor",
    }
    assert runner.TASKS["sync"][0] == ("bootstrap",)
    assert runner.TASKS["test"][0] == ("validate",)
    assert runner.TASKS["lint"][0] == ("sync", "workflow-lint")
    assert runner.TASKS["all"][0] == ("test", "lint", "web", "book", "proof")


def test_make_and_native_wrappers_delegate_to_the_same_python_runner() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    posix = (ROOT / "dev").read_text(encoding="utf-8")
    powershell = (ROOT / "dev.ps1").read_text(encoding="utf-8")
    shell_bootstrap = (ROOT / "scripts/bootstrap-tools.sh").read_text(encoding="utf-8")
    powershell_bootstrap = (ROOT / "scripts/bootstrap-tools.ps1").read_text(encoding="utf-8")

    for target in (
        "bootstrap",
        "sync",
        "artifact-audit",
        "validate",
        "test",
        "lint",
        "workflow-lint",
        "web",
        "review",
        "book",
        "proof",
        "all",
        "preview",
        "clean",
    ):
        assert f"{target}:\n\t$(DEV) {target}" in makefile
    assert "DEV := ./scripts/bootstrap-tools.sh" in makefile
    assert "/bin/bash" not in makefile
    assert 'exec "$ROOT/scripts/bootstrap-tools.sh" "$@"' in posix
    assert "scripts\\dev.py" in powershell
    assert "py -ErrorAction" in powershell
    assert 'exec "$PYTHON_BIN" "$ROOT/scripts/dev.py" "$@"' in shell_bootstrap
    assert "'dev.ps1') bootstrap" in powershell_bootstrap
    if os.name != "nt":
        assert (ROOT / "dev").stat().st_mode & stat.S_IXUSR


def test_native_wrappers_pin_the_reviewed_runner_and_manifest() -> None:
    runner_hash = hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    shell = (ROOT / "scripts/bootstrap-tools.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "dev.ps1").read_text(encoding="utf-8")

    assert f"EXPECTED_RUNNER_SHA256='{runner_hash}'" in shell
    assert f"EXPECTED_MANIFEST_SHA256='{manifest_hash}'" in shell
    assert f"$expectedRunnerSha256 = '{runner_hash}'" in powershell
    assert f"$expectedManifestSha256 = '{manifest_hash}'" in powershell


def test_quarto_pre_render_uses_the_active_python_on_every_os() -> None:
    quarto = (ROOT / "_quarto.yml").read_text(encoding="utf-8")
    hook = (ROOT / "platform/scripts/quarto_pre_render.py").read_text(encoding="utf-8")

    assert "python platform/scripts/quarto_pre_render.py" in quarto
    assert ".tools/uv/uv" not in quarto
    assert "sys.executable" in hook
    assert "shell=True" not in hook


def test_runner_refuses_to_remove_any_path_outside_the_checkout(tmp_path: Path) -> None:
    runner = load_runner()

    with pytest.raises(runner.DevError, match="outside the repository"):
        runner._safe_remove(tmp_path)


def test_node_tar_extraction_skips_unneeded_package_manager_symlinks(
    tmp_path: Path,
) -> None:
    runner = load_runner()
    archive = tmp_path / "node.tar.gz"
    payload = b"node"
    with tarfile.open(archive, "w:gz") as packed:
        directory = tarfile.TarInfo("node/bin")
        directory.type = tarfile.DIRTYPE
        packed.addfile(directory)
        executable = tarfile.TarInfo("node/bin/node")
        executable.size = len(payload)
        packed.addfile(executable, io.BytesIO(payload))
        npm = tarfile.TarInfo("node/bin/npm")
        npm.type = tarfile.SYMTYPE
        npm.linkname = "../lib/node_modules/npm/bin/npm-cli.js"
        packed.addfile(npm)

    destination = tmp_path / "extracted"
    destination.mkdir()
    runner._extract_archive("node", archive, destination)

    assert (destination / "node/bin/node").read_bytes() == payload
    assert not (destination / "node/bin/npm").exists()
