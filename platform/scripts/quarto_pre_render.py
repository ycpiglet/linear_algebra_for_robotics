"""Run Quarto pre-render generators with the active project Python."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    commands = (
        ("platform/scripts/atlas.py", "build"),
        ("platform/scripts/glossary.py", "build"),
        ("platform/scripts/pagehistory.py", "build"),
    )
    for command in commands:
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
