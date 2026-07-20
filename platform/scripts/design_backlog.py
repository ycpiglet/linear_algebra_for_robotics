#!/usr/bin/env python3
"""Validate and list the publishing design operations backlog."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - incomplete environment only
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - incomplete environment only
    raise SystemExit("jsonschema is required: python -m pip install jsonschema") from exc


ROOT = Path(__file__).resolve().parents[2]
ITEMS_DIR = Path("platform/design/work-items")
SCHEMA_PATH = Path("platform/schemas/design-work-item.schema.json")
ACTIVE_STATES = {"in_progress", "in_review"}
STARTABLE_STATES = {"ready", "in_progress", "in_review", "done"}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    source: str | None = None

    def __str__(self) -> str:
        prefix = f"{self.source}: " if self.source else ""
        return f"{prefix}[{self.code}] {self.message}"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_mapping(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return None, str(exc)
    if not isinstance(loaded, dict):
        return None, "document must be a YAML mapping"
    return loaded, None


def _schema_diagnostics(
    item: dict[str, Any], path: Path, validator: Draft202012Validator, root: Path
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for error in sorted(validator.iter_errors(item), key=lambda value: list(value.path)):
        pointer = ".".join(str(part) for part in error.path) or "$"
        diagnostics.append(
            Diagnostic(
                "schema.invalid",
                f"{pointer}: {error.message}",
                _relative(path, root),
            )
        )
    return diagnostics


def _cycle_diagnostics(items: dict[str, dict[str, Any]]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    visiting: list[str] = []
    visited: set[str] = set()
    reported: set[tuple[str, ...]] = set()

    def visit(identifier: str) -> None:
        if identifier in visited:
            return
        if identifier in visiting:
            start = visiting.index(identifier)
            cycle = tuple(visiting[start:] + [identifier])
            if cycle not in reported:
                diagnostics.append(
                    Diagnostic("dependency.cycle", " -> ".join(cycle), f"{identifier}.yml")
                )
                reported.add(cycle)
            return
        visiting.append(identifier)
        for dependency in items[identifier].get("dependencies", []):
            if dependency in items:
                visit(dependency)
        visiting.pop()
        visited.add(identifier)

    for identifier in sorted(items):
        visit(identifier)
    return diagnostics


def validate_backlog(root: Path = ROOT) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    items_dir = root / ITEMS_DIR
    schema_path = root / SCHEMA_PATH
    diagnostics: list[Diagnostic] = []
    items: dict[str, dict[str, Any]] = {}

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        return {}, [Diagnostic("schema.unavailable", str(exc), _relative(schema_path, root))]
    validator = Draft202012Validator(schema)

    for path in sorted(items_dir.glob("*.yml")):
        item, error = _read_mapping(path)
        source = _relative(path, root)
        if error:
            diagnostics.append(Diagnostic("yaml.invalid", error, source))
            continue
        assert item is not None
        diagnostics.extend(_schema_diagnostics(item, path, validator, root))
        identifier = item.get("id")
        if not isinstance(identifier, str):
            continue
        if path.stem != identifier:
            diagnostics.append(
                Diagnostic(
                    "id.filename_mismatch",
                    f"file stem {path.stem!r} must match id {identifier!r}",
                    source,
                )
            )
        if identifier in items:
            diagnostics.append(Diagnostic("id.duplicate", f"duplicate id {identifier}", source))
            continue
        items[identifier] = item

    if not items:
        diagnostics.append(
            Diagnostic("items.empty", "no design work items found", _relative(items_dir, root))
        )
        return items, diagnostics

    for identifier, item in sorted(items.items()):
        source = f"{(ITEMS_DIR / f'{identifier}.yml').as_posix()}"
        for dependency in item.get("dependencies", []):
            if dependency not in items:
                diagnostics.append(
                    Diagnostic("dependency.missing", f"unknown dependency {dependency}", source)
                )
        status = item.get("status")
        if status in STARTABLE_STATES:
            unfinished = [
                dependency
                for dependency in item.get("dependencies", [])
                if dependency in items and items[dependency].get("status") != "done"
            ]
            if unfinished:
                diagnostics.append(
                    Diagnostic(
                        "dependency.unfinished",
                        f"status {status} requires done dependencies: {', '.join(unfinished)}",
                        source,
                    )
                )
            for key in ("source_contract",):
                if not item.get("verification", {}).get(key):
                    diagnostics.append(
                        Diagnostic(
                            "verification.missing",
                            f"verification.{key} is required",
                            source,
                        )
                    )
            if not item.get("rollback", {}).get("triggers"):
                diagnostics.append(
                    Diagnostic("rollback.missing", "rollback.triggers is required", source)
                )
            if not item.get("definition_of_done"):
                diagnostics.append(
                    Diagnostic("completion.missing", "definition_of_done is required", source)
                )
        if status in ACTIVE_STATES and not item.get("branch"):
            diagnostics.append(
                Diagnostic("branch.missing", f"status {status} requires branch", source)
            )
        if status == "decision" and not item.get("decision_needed"):
            diagnostics.append(
                Diagnostic("decision.missing", "decision status requires decision_needed", source)
            )
        if status == "blocked" and not item.get("blocker"):
            diagnostics.append(
                Diagnostic("blocker.missing", "blocked status requires blocker", source)
            )
        if status == "done":
            evidence = item.get("evidence", {})
            if not evidence.get("pr") or not evidence.get("ci_runs"):
                diagnostics.append(
                    Diagnostic(
                        "evidence.missing",
                        "done status requires PR and CI evidence",
                        source,
                    )
                )

    diagnostics.extend(_cycle_diagnostics(items))

    locks: dict[str, list[str]] = defaultdict(list)
    for identifier, item in items.items():
        if item.get("status") not in ACTIVE_STATES:
            continue
        for lock in item.get("change_paths", {}).get("exclusive_locks", []):
            locks[lock].append(identifier)
    for lock, owners in sorted(locks.items()):
        if len(owners) > 1:
            diagnostics.append(
                Diagnostic(
                    "lock.conflict",
                    f"exclusive lock {lock!r} is active in {', '.join(sorted(owners))}",
                )
            )

    return items, diagnostics


def _print_items(items: dict[str, dict[str, Any]], output_format: str) -> None:
    ordered = sorted(items.values(), key=lambda item: (item["priority"], item["id"]))
    if output_format == "json":
        print(json.dumps(ordered, ensure_ascii=False, indent=2))
        return
    if output_format == "markdown":
        print("| ID | Priority | Status | Area | Title | Dependencies |")
        print("|---|---|---|---|---|---|")
        for item in ordered:
            dependencies = ", ".join(item["dependencies"]) or "—"
            print(
                f"| {item['id']} | {item['priority']} | {item['status']} | "
                f"{item['area']} | {item['title']} | {dependencies} |"
            )
        return
    for item in ordered:
        dependencies = ",".join(item["dependencies"]) or "-"
        print(
            f"{item['id']:<7} {item['priority']:<2} {item['status']:<12} "
            f"deps={dependencies:<23} {item['title']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate schemas, dependencies, states, and locks")
    list_parser = subparsers.add_parser("list", help="list work items after validation")
    list_parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    arguments = parser.parse_args(argv)

    items, diagnostics = validate_backlog()
    for diagnostic in diagnostics:
        print(diagnostic, file=sys.stderr)
    if diagnostics:
        return 1
    if arguments.command == "list":
        _print_items(items, arguments.format)
    else:
        print(f"design backlog: {len(items)} work items valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
