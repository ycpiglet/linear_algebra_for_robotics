#!/usr/bin/env python3
"""Compatibility entry point used by Quarto and Make.

No arguments builds manifests.  ``--check`` validates source metadata and graph
integrity without requiring generated files to exist.  Use ``--check-generated``
in CI when committed manifests must be proven current.
"""

from __future__ import annotations

import sys

from atlas import main


def translate(arguments: list[str]) -> list[str]:
    if "--check-generated" in arguments:
        translated = ["--check" if item == "--check-generated" else item for item in arguments]
        return ["build", *translated]
    if "--check" in arguments:
        return ["validate", *[item for item in arguments if item != "--check"]]
    return ["build", *arguments]


if __name__ == "__main__":
    raise SystemExit(main(translate(sys.argv[1:])))
