#!/usr/bin/env python3
"""Collect per-page git history for the review build's footer (Phase 2-3).

Runs as a Quarto pre-render step and writes
``platform/generated/page-history.json`` mapping each rendered source path to
its latest commits (sha, date, author, subject).  The review build's footer
widget renders this client-side; the reader build ships the JSON but shows
no widget.  On a shallow clone the history is simply shorter — the script
never fails the build over missing history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("platform/generated/page-history.json")
LIMIT = 3

# Mirrors the render globs of _quarto-web.yml (platform/** is excluded there).
SOURCE_GLOBS = ("*.qmd", "content/**/*.qmd", "courseware/labs/*.qmd")


def rendered_sources(root: Path) -> list[Path]:
    seen: set[Path] = set()
    for pattern in SOURCE_GLOBS:
        seen.update(root.glob(pattern))
    return sorted(path for path in seen if path.is_file())


def history(root: Path, path: Path, limit: int = LIMIT) -> list[dict[str, str]]:
    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "log", f"-n{limit}",
             "--format=%H%x1f%aI%x1f%an%x1f%s", "--", str(path.relative_to(root))],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    entries = []
    for line in raw.splitlines():
        sha, date, author, subject = line.split("\x1f", 3)
        entries.append({"sha": sha, "date": date[:10], "author": author, "subject": subject})
    return entries


def build(root: Path = ROOT) -> Path:
    data = {
        str(path.relative_to(root)): entries
        for path in rendered_sources(root)
        if (entries := history(root, path))
    }
    output = root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="write platform/generated/page-history.json")
    parser.parse_args(argv)
    output = build()
    pages = len(json.loads(output.read_text(encoding="utf-8")))
    print(f"page-history: {pages}개 페이지 이력 기록 → {output.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
