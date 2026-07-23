#!/usr/bin/env python3
"""Cross-platform developer entrypoint for Windows, macOS, and Linux."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
MANIFEST_PATH = ROOT / "scripts" / "toolchain.json"
VENV = ROOT / ".venv"
VENV_STATE = VENV / ".atlas-environment.json"


class DevError(RuntimeError):
    """A user-actionable development environment error."""


def platform_key(
    system: str | None = None,
    machine: str | None = None,
) -> str:
    system_name = (system or platform.system()).lower()
    machine_name = (machine or platform.machine()).lower()
    systems = {
        "darwin": "macos",
        "linux": "linux",
        "windows": "windows",
    }
    machines = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    try:
        return f"{systems[system_name]}-{machines[machine_name]}"
    except KeyError as exc:
        raise DevError(
            f"Unsupported development platform: system={system_name}, machine={machine_name}"
        ) from exc


def load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("tools"), dict):
        raise DevError(f"Unsupported toolchain manifest: {MANIFEST_PATH}")
    return data


def asset_for(tool_name: str, key: str | None = None) -> dict[str, str]:
    selected_key = key or platform_key()
    tool = load_manifest()["tools"][tool_name]
    try:
        asset = tool["assets"][selected_key]
    except KeyError as exc:
        supported = ", ".join(sorted(tool["assets"]))
        raise DevError(
            f"{tool_name} does not support {selected_key}; supported platforms: {supported}"
        ) from exc
    return asset


def tool_path(tool_name: str, key: str | None = None) -> Path:
    manifest = load_manifest()
    tool = manifest["tools"][tool_name]
    asset = asset_for(tool_name, key)
    return TOOLS / tool["install_dir"] / Path(PurePosixPath(asset["executable"]))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(tool_name: str, asset: dict[str, str]) -> Path:
    downloads = TOOLS / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.urlparse(asset["url"]).path).name
    target = downloads / f"{asset['sha256']}-{filename}"
    if target.is_file() and _sha256(target) == asset["sha256"]:
        return target
    if target.exists():
        target.unlink()

    print(f"Downloading {tool_name}: {filename}", flush=True)
    request = urllib.request.Request(
        asset["url"],
        headers={"User-Agent": "robotics-math-atlas-toolchain/1"},
    )
    temporary = target.with_suffix(f"{target.suffix}.part")
    if temporary.exists():
        temporary.unlink()
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != asset["sha256"]:
            raise DevError(
                f"{tool_name} SHA-256 mismatch: expected {asset['sha256']}, got {actual}"
            )
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def _validate_archive_name(name: str) -> None:
    normalized = PurePosixPath(name.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise DevError(f"Unsafe archive member: {name}")


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    _validate_archive_name(member.name)
    if not (
        member.isfile()
        or member.isdir()
        or member.issym()
        or member.islnk()
    ):
        raise DevError(f"Unsupported tar member type: {member.name}")
    if not (member.issym() or member.islnk()):
        return

    target = PurePosixPath(member.linkname.replace("\\", "/"))
    if target.is_absolute():
        raise DevError(f"Unsafe archive link target: {member.name} -> {member.linkname}")
    base = PurePosixPath(member.name).parent if member.issym() else PurePosixPath()
    resolved: list[str] = []
    for part in (*base.parts, *target.parts):
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved:
                raise DevError(
                    f"Unsafe archive link target: {member.name} -> {member.linkname}"
                )
            resolved.pop()
        else:
            resolved.append(part)


def _extract_archive(tool_name: str, archive: Path, destination: Path) -> None:
    filename = archive.name.lower()
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                _validate_archive_name(member.filename)
            zipped.extractall(destination)
        return
    if filename.endswith((".tar.gz", ".tgz", ".tar.xz")):
        with tarfile.open(archive) as packed:
            members = packed.getmembers()
            for member in members:
                _validate_tar_member(member)

            # Apple's bsdtar restores the signed xattrs included in the
            # official Quarto macOS archive; Python's tarfile intentionally
            # does not. Preserve those attributes on native macOS.
            if platform.system().lower() == "darwin":
                subprocess.run(
                    ["/usr/bin/tar", "-xf", archive, "-C", destination],
                    check=True,
                    shell=False,
                )
                return

            # Node's Unix archives contain npm/npx/corepack relative symlinks.
            # The atlas needs only the node executable, and older Python
            # security backports can incorrectly classify those links as
            # escaping the destination. Skip them instead of weakening the
            # extraction filter for the whole archive.
            def extraction_filter(
                member: tarfile.TarInfo,
                path: str,
            ) -> tarfile.TarInfo | None:
                if tool_name == "node" and (member.issym() or member.islnk()):
                    return None
                return tarfile.data_filter(member, path)

            if hasattr(tarfile, "data_filter"):
                packed.extractall(destination, members=members, filter=extraction_filter)
            else:  # Python versions without the safe extraction API.
                regular_members = [
                    member for member in members if member.isfile() or member.isdir()
                ]
                packed.extractall(destination, members=regular_members)
        return
    raise DevError(f"Unsupported archive format: {archive.name}")


def _find_install_root(extracted: Path, executable: str) -> Path:
    expected = PurePosixPath(executable).parts
    matches: list[Path] = []
    for candidate in extracted.rglob(expected[-1]):
        relative = PurePosixPath(candidate.relative_to(extracted).as_posix()).parts
        if len(relative) >= len(expected) and tuple(relative[-len(expected) :]) == expected:
            matches.append(candidate)
    if len(matches) != 1:
        rendered = ", ".join(str(path.relative_to(extracted)) for path in matches)
        raise DevError(
            f"Expected exactly one {executable} in archive, found {len(matches)}: {rendered}"
        )
    root = matches[0]
    for _ in expected:
        root = root.parent
    return root


def _install_tool(tool_name: str, key: str) -> None:
    manifest = load_manifest()
    tool = manifest["tools"][tool_name]
    asset = asset_for(tool_name, key)
    install_dir = TOOLS / tool["install_dir"]
    executable = install_dir / Path(PurePosixPath(asset["executable"]))
    state_path = install_dir / ".atlas-tool.json"
    expected_state = {
        "tool": tool_name,
        "version": tool["version"],
        "platform": key,
        "sha256": asset["sha256"],
        "executable": asset["executable"],
    }
    if executable.is_file() and state_path.is_file():
        try:
            if json.loads(state_path.read_text(encoding="utf-8")) == expected_state:
                return
        except (OSError, json.JSONDecodeError):
            pass

    archive = _download(tool_name, asset)
    staging_root = TOOLS / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{tool_name}-", dir=staging_root))
    extracted = staging / "extracted"
    prepared = staging / "prepared"
    extracted.mkdir()
    prepared.mkdir()
    try:
        _extract_archive(tool_name, archive, extracted)
        archive_root = _find_install_root(extracted, asset["executable"])
        for child in archive_root.iterdir():
            shutil.move(str(child), prepared / child.name)
        prepared_executable = prepared / Path(PurePosixPath(asset["executable"]))
        if not prepared_executable.is_file():
            raise DevError(f"{tool_name} executable was not prepared: {prepared_executable}")
        if os.name != "nt":
            prepared_executable.chmod(
                prepared_executable.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
        if install_dir.exists():
            _safe_remove(install_dir)
        prepared.replace(install_dir)
        state_path.write_text(
            json.dumps(expected_state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        if staging.exists():
            _safe_remove(staging)


def _safe_remove(path: Path) -> None:
    root = ROOT.resolve()
    candidate = path.resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise DevError(f"Refusing to remove path outside the repository: {path}")
    if candidate.is_dir() and not candidate.is_symlink():
        shutil.rmtree(candidate)
    elif candidate.exists() or candidate.is_symlink():
        candidate.unlink()


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _development_env(*, include_venv: bool = True) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["UV_PYTHON_INSTALL_DIR"] = str(TOOLS / "python")
    env["UV_CACHE_DIR"] = str(TOOLS / "uv-cache")
    env["UV_PROJECT_ENVIRONMENT"] = str(VENV)
    env["UV_MANAGED_PYTHON"] = "1"
    path_entries: list[str] = []
    if include_venv and _venv_python().is_file():
        path_entries.append(str(_venv_python().parent))
        env["QUARTO_PYTHON"] = str(_venv_python())
    for tool_name in ("node", "typst", "quarto", "uv"):
        candidate = tool_path(tool_name)
        if candidate.is_file():
            path_entries.append(str(candidate.parent))
    if tool_path("typst").is_file():
        env["QUARTO_TYPST"] = str(tool_path("typst"))
    path_entries.append(env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(entry for entry in path_entries if entry)
    return env


def _display_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(command)) if os.name == "nt" else " ".join(command)


def _run(
    command: Sequence[str | os.PathLike[str]],
    *,
    env: dict[str, str] | None = None,
) -> None:
    normalized = [os.fspath(part) for part in command]
    print(f"+ {_display_command(normalized)}", flush=True)
    subprocess.run(
        normalized,
        cwd=ROOT,
        env=env or _development_env(),
        check=True,
        shell=False,
    )


def _run_tool(tool_name: str, *arguments: str, include_venv: bool = True) -> None:
    executable = tool_path(tool_name)
    if not executable.is_file():
        raise DevError(f"{tool_name} is not installed; run bootstrap first")
    _run([executable, *arguments], env=_development_env(include_venv=include_venv))


def _run_uv(*arguments: str) -> None:
    _run_tool("uv", *arguments)


def _remove_nested_outputs(output: Path, names: Sequence[str]) -> None:
    for name in names:
        nested = output / name
        if nested.exists():
            _safe_remove(nested)


def task_bootstrap() -> None:
    key = platform_key()
    manifest = load_manifest()
    unsupported = [
        name for name, tool in manifest["tools"].items() if key not in tool["assets"]
    ]
    if unsupported:
        raise DevError(f"{key} is missing tool assets: {', '.join(unsupported)}")
    TOOLS.mkdir(parents=True, exist_ok=True)
    for tool_name in manifest["tools"]:
        _install_tool(tool_name, key)
    _run_tool(
        "uv",
        "python",
        "install",
        manifest["python_version"],
        "--no-bin",
        "--no-registry",
        include_venv=False,
    )


def task_sync() -> None:
    expected_state = {
        "platform": platform_key(),
        "repository": str(ROOT.resolve()),
        "python": load_manifest()["python_version"],
    }
    if VENV.exists():
        try:
            current_state = json.loads(VENV_STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_state = None
        if current_state != expected_state:
            print("Recreating the generated virtual environment for this OS/path.", flush=True)
            _safe_remove(VENV)
    _run_uv(
        "sync",
        "--python",
        load_manifest()["python_version"],
        "--group",
        "dev",
        "--locked",
    )
    VENV_STATE.write_text(
        json.dumps(expected_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def task_artifact_audit() -> None:
    _run_uv(
        "run",
        "--locked",
        "python",
        "platform/scripts/artifact_inventory.py",
        "check",
    )
    _run_uv(
        "run",
        "--locked",
        "python",
        "platform/scripts/artifact_inventory.py",
        "regenerate",
    )


def task_validate() -> None:
    commands = (
        ("platform/scripts/atlas.py", "build"),
        ("platform/scripts/atlas.py", "build", "--check"),
        ("platform/scripts/glossary.py", "build"),
        ("platform/scripts/glossary.py", "build", "--check"),
        ("platform/scripts/editorial.py", "lint"),
        ("platform/scripts/design_backlog.py", "check"),
        ("platform/scripts/artifact_inventory.py", "check"),
    )
    for command in commands:
        _run_uv("run", "--locked", "python", *command)


def task_test() -> None:
    _run_uv("run", "--locked", "pytest")


def task_workflow_lint() -> None:
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    _run(
        [
            tool_path("actionlint"),
            "-shellcheck",
            tool_path("shellcheck"),
            *(path.relative_to(ROOT) for path in workflow_paths),
        ]
    )


def task_lint() -> None:
    _run_uv("run", "--locked", "ruff", "check", "platform", "courseware", "scripts")


def _render(profile: str, output_name: str) -> Path:
    output = ROOT / output_name
    if output.exists():
        _safe_remove(output)
    _run_tool("quarto", "render", "--profile", profile)
    return output


def task_web() -> None:
    output = _render("web", "_site")
    _remove_nested_outputs(output, ("_site", "_book", "_proof"))
    _run_uv("run", "--locked", "python", "scripts/verify_outputs.py", "_site")


def task_review() -> None:
    # Quarto gives the first profile precedence for scalar values.
    output = _render("review,web", "_review")
    _remove_nested_outputs(output, ("_site", "_book", "_proof", "_review"))
    _run_uv("run", "--locked", "python", "scripts/verify_outputs.py", "_review")


def _single_nonempty(pattern: str, label: str) -> Path:
    matches = [path for path in ROOT.glob(pattern) if path.is_file() and path.stat().st_size]
    if len(matches) != 1:
        raise DevError(f"Expected one non-empty {label}, found {len(matches)}")
    return matches[0]


def task_book() -> None:
    output = _render("book", "_book")
    _remove_nested_outputs(output, ("_site", "_book", "_proof"))
    epub = _single_nonempty("_book/*.epub", "EPUB")
    pdf = _single_nonempty("_book/*.pdf", "PDF")
    _run_uv(
        "run",
        "--locked",
        "python",
        "scripts/package_epub_assets.py",
        epub.relative_to(ROOT),
    )
    _run_uv(
        "run",
        "--locked",
        "python",
        "scripts/verify_outputs.py",
        "_book",
        epub.relative_to(ROOT),
        pdf.relative_to(ROOT),
    )


def task_proof() -> None:
    output = _render("proof", "_proof")
    _remove_nested_outputs(output, ("_site", "_book", "_proof"))
    pdf = _single_nonempty("_proof/*.pdf", "proof PDF")
    _run_uv(
        "run",
        "--locked",
        "python",
        "scripts/verify_outputs.py",
        "_proof",
        pdf.relative_to(ROOT),
    )


def task_preview() -> None:
    _run_tool("quarto", "preview", "--profile", "web")


def task_clean() -> None:
    paths = (
        "_site",
        "_review",
        "_book",
        "_proof",
        ".quarto",
        "platform/generated",
        "courseware/labs/.jupyter_cache",
    )
    for relative in paths:
        path = ROOT / relative
        if path.exists():
            _safe_remove(path)


def task_doctor() -> None:
    print(f"platform={platform_key()}")
    print(f"repository={ROOT}")
    print(f"bootstrap_python={sys.version.split()[0]}")
    print(f"project_python={load_manifest()['python_version']}")
    for tool_name in load_manifest()["tools"]:
        executable = tool_path(tool_name)
        state = "installed" if executable.is_file() else "missing"
        print(f"{tool_name}={executable} ({state})")
    venv_state = "installed" if _venv_python().is_file() else "missing"
    print(f"venv={_venv_python()} ({venv_state})")


Task = tuple[tuple[str, ...], Callable[[], None]]
TASKS: dict[str, Task] = {
    "bootstrap": ((), task_bootstrap),
    "sync": (("bootstrap",), task_sync),
    "artifact-audit": (("sync",), task_artifact_audit),
    "validate": (("sync",), task_validate),
    "test": (("validate",), task_test),
    "workflow-lint": (("bootstrap",), task_workflow_lint),
    "lint": (("sync", "workflow-lint"), task_lint),
    "web": (("validate",), task_web),
    "review": (("validate",), task_review),
    "book": (("validate",), task_book),
    "proof": (("validate",), task_proof),
    "all": (("test", "lint", "web", "book", "proof"), lambda: None),
    "preview": (("validate",), task_preview),
    "clean": ((), task_clean),
    "doctor": ((), task_doctor),
}


class TaskRunner:
    def __init__(self) -> None:
        self.completed: set[str] = set()

    def run(self, name: str) -> None:
        if name in self.completed:
            return
        dependencies, action = TASKS[name]
        for dependency in dependencies:
            self.run(dependency)
        print(f"==> {name}", flush=True)
        action()
        self.completed.add(name)


def main() -> int:
    if sys.version_info < (3, 9):  # noqa: UP036 - bootstrap precedes project Python
        print(
            "error: the bootstrap runner requires Python 3.9 or newer; "
            "install Python 3.12 and try again",
            file=sys.stderr,
        )
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", nargs="+", choices=sorted(TASKS))
    arguments = parser.parse_args()
    runner = TaskRunner()
    try:
        for task in arguments.tasks:
            runner.run(task)
    except (DevError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
