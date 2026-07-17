#!/usr/bin/env python3
"""Validate the glossary source and render a deterministic Quarto fragment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("platform/glossary/glossary.yml")
SCHEMA = Path("platform/schemas/glossary.schema.json")
OUTPUT = Path("platform/generated/glossary.qmd")


def load_and_validate(root: Path) -> dict[str, Any]:
    source = root / SOURCE
    schema_path = root / SCHEMA
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data),
        key=lambda item: list(item.path),
    )
    if errors:
        messages = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise ValueError("Glossary schema validation failed:\n" + "\n".join(messages))

    terms = data["terms"]
    identifiers = [term["id"] for term in terms]
    duplicates = sorted(
        {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    )
    if duplicates:
        raise ValueError(f"Duplicate glossary id(s): {', '.join(duplicates)}")
    known = set(identifiers)
    unresolved = sorted(
        {
            target
            for term in terms
            for target in term.get("related", [])
            if target not in known
        }
    )
    if unresolved:
        raise ValueError(f"Unknown related glossary id(s): {', '.join(unresolved)}")
    return data


def render(data: dict[str, Any]) -> str:
    terms = sorted(data["terms"], key=lambda term: (term["ko"], term["id"]))
    labels = {term["id"]: term["ko"] for term in terms}
    lines = [
        "<!-- Generated from platform/glossary/glossary.yml; do not edit directly. -->",
        "",
        ":::: {.glossary-grid}",
    ]
    for term in terms:
        english = f'<span lang="en">{term["en"]}</span>'
        abbreviation = ""
        if term.get("abbr"):
            abbreviation = f' · <abbr title="{term["en"]} — {term["ko"]}">{term["abbr"]}</abbr>'
        lines.extend(
            [
                f'::: {{.glossary-entry #term-{term["id"]}}}',
                f'### {term["ko"]} · {english}{abbreviation}',
                "",
                term["short"],
                "",
            ]
        )
        if term.get("notation"):
            lines.extend([f'**대표 표기:** {term["notation"]}', ""])
        if term.get("aliases"):
            lines.extend([f'**다른 표기:** {", ".join(term["aliases"])}', ""])
        if term.get("related"):
            related = ", ".join(
                f'[{labels[target]}](#term-{target})' for target in term["related"]
            )
            lines.extend([f"**같이 보기:** {related}", ""])
        lines.extend([":::", ""])
    lines.extend(["::::", ""])
    return "\n".join(lines)


def build(root: Path, *, check: bool = False) -> None:
    rendered = render(load_and_validate(root))
    output = root / OUTPUT
    if check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise ValueError(f"Generated glossary is stale: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build", nargs="?", default="build")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        build(args.root.resolve(), check=args.check)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print("Glossary validation passed." if args.check else f"Generated {OUTPUT}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
