#!/usr/bin/env python3
"""Validate and list the publishing design operations backlog."""

from __future__ import annotations

import argparse
import json
import re
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
LOCK_HOLDING_STATES = ACTIVE_STATES | {"blocked"}
STARTABLE_STATES = {"ready", "in_progress", "in_review", "blocked", "done"}
EVIDENCE_STATES = {"in_review", "done", "rolled_back"}
CORE_SCHEMA_FIELDS = {
    "schema_version",
    "id",
    "status",
    "change_paths",
    "verification",
    "rollback",
    "evidence",
}
CORE_EVIDENCE_FIELDS = {
    "pr",
    "ci_runs",
    "rendered_artifacts",
    "post_merge",
    "last_known_good",
    "revert_ref",
    "follow_up",
}
ALLOWED_STATES = {
    "decision",
    "planned",
    "ready",
    "in_progress",
    "in_review",
    "blocked",
    "done",
    "cancelled",
    "superseded",
    "rolled_back",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    if not isinstance(node, yaml.nodes.MappingNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            f"expected a mapping node, but found {node.id}",
            node.start_mark,
        )
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    source: str | None = None

    def __str__(self) -> str:
        prefix = f"{self.source}: " if self.source else ""
        value = f"{prefix}[{self.code}] {self.message}"
        return value.encode("utf-8", errors="backslashreplace").decode("utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_mapping(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return None, str(exc)
    if not isinstance(loaded, dict):
        return None, "document must be a YAML mapping"
    return loaded, None


def _is_path_spec(value: str) -> bool:
    """Return whether a value is an unambiguous repository-relative path or glob."""

    if not value or value.startswith(("/", "~")) or "\\" in value or any(
        character in value for character in "[]"
    ):
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.IGNORECASE):
        return False
    if any(part in {"", ".", ".."} for part in value.split("/")):
        return False
    return not any(character.isspace() for character in value)


def _is_valid_short_branch(value: str) -> bool:
    if (
        not value
        or value in {"@", "HEAD", "main"}
        or value.startswith(("-", "/", "refs/"))
        or value.endswith(("/", "."))
        or ".." in value
        or "//" in value
        or "@{" in value
        or any(character in value for character in " ~^:?*[\\")
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock")
        for part in value.split("/")
    )


def _text_contract_error(value: Any, path: str = "$") -> str | None:
    if isinstance(value, str):
        if not value.strip():
            return f"{path} contains a blank string"
        if "\x00" in value or any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            return f"{path} contains unsafe Unicode"
        return None
    if isinstance(value, list):
        for index, entry in enumerate(value):
            error = _text_contract_error(entry, f"{path}[{index}]")
            if error:
                return error
    elif isinstance(value, dict):
        for key, entry in value.items():
            error = _text_contract_error(key, f"{path}.<key>")
            if error:
                return error
            error = _text_contract_error(entry, f"{path}.{key}")
            if error:
                return error
    return None


def _semantic_shape_error(item: dict[str, Any]) -> str | None:
    """Protect semantic checks even if the JSON Schema is weakened in the same diff."""

    required = {
        "schema_version",
        "id",
        "title",
        "area",
        "status",
        "priority",
        "change_class",
        "version_impact",
        "owner_role",
        "review_roles",
        "branch",
        "dependencies",
        "decision_refs",
        "decision_needed",
        "blocker",
        "status_reason",
        "superseded_by",
        "scope",
        "change_paths",
        "verification",
        "rollback",
        "definition_of_done",
        "evidence",
        "last_reviewed",
    }
    missing = sorted(required - item.keys())
    if missing:
        return f"semantic contract fields are missing: {', '.join(missing)}"
    for key in (
        "id",
        "title",
        "area",
        "priority",
        "change_class",
        "version_impact",
        "owner_role",
        "last_reviewed",
    ):
        if not isinstance(item[key], str):
            return f"{key} must be a string"
    if (
        type(item["schema_version"]) is not int
        or item["schema_version"] != 1
        or not isinstance(item["status"], str)
        or item["status"] not in ALLOWED_STATES
    ):
        return "schema_version or status violates the semantic contract"
    for key in ("branch", "blocker", "status_reason", "superseded_by"):
        if item[key] is not None and not isinstance(item[key], str):
            return f"{key} must be a string or null"
    for key in (
        "review_roles",
        "dependencies",
        "decision_refs",
        "decision_needed",
        "definition_of_done",
    ):
        if not isinstance(item[key], list) or not all(
            isinstance(value, str) for value in item[key]
        ):
            return f"{key} must be a string list"

    nested_lists = {
        "scope": ("in", "out"),
        "change_paths": ("read", "write", "exclusive_locks", "generated"),
        "verification": ("source_contract", "rendered_contract", "post_merge"),
        "rollback": ("triggers", "steps", "compatibility_preserved"),
        "evidence": ("ci_runs", "rendered_artifacts", "post_merge"),
    }
    for field, list_keys in nested_lists.items():
        value = item[field]
        if not isinstance(value, dict):
            return f"{field} must be a mapping"
        for key in list_keys:
            if key not in value or not isinstance(value[key], list) or not all(
                isinstance(entry, str) for entry in value[key]
            ):
                return f"{field}.{key} must be a string list"
    evidence = item["evidence"]
    for key in ("issue", "pr"):
        if evidence.get(key) is not None and (
            type(evidence[key]) is not int or evidence[key] < 1
        ):
            return f"evidence.{key} must be a positive integer or null"
    for key in ("last_known_good", "revert_ref", "follow_up"):
        if evidence.get(key) is not None and not isinstance(evidence[key], str):
            return f"evidence.{key} must be a string or null"
    if not isinstance(item["rollback"].get("unit"), str):
        return "rollback.unit must be a string"
    return None


def _heading_slug(title: str) -> str:
    title = re.sub(r"\s+\{[^{}]*\}\s*$", "", title.strip()).lower()
    title = re.sub(r"\s+#+\s*$", "", title)
    title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    return re.sub(r"\s+", "-", title)


def _markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    fence_character: str | None = None
    fence_length = 0
    previous_line: str | None = None
    in_comment = False
    lines = text.splitlines()
    in_front_matter = bool(lines and lines[0].strip() == "---")

    for index, line in enumerate(lines):
        if in_front_matter:
            if index > 0 and line.strip() in {"---", "..."}:
                in_front_matter = False
            continue

        if fence_character is not None:
            closing_fence = re.match(r"^\s{0,3}(`{3,}|~{3,})\s*$", line)
            if closing_fence:
                marker = closing_fence.group(1)
                if marker[0] == fence_character and len(marker) >= fence_length:
                    fence_character = None
                    fence_length = 0
            previous_line = None
            continue

        visible_parts: list[str] = []
        remainder = line
        while remainder:
            if in_comment:
                closing = remainder.find("-->")
                if closing < 0:
                    remainder = ""
                    continue
                in_comment = False
                remainder = remainder[closing + 3 :]
                continue
            opening = remainder.find("<!--")
            if opening < 0:
                visible_parts.append(remainder)
                break
            visible_parts.append(remainder[:opening])
            remainder = remainder[opening + 4 :]
            in_comment = True
        line = "".join(visible_parts)
        if not line.strip():
            previous_line = None
            continue

        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            previous_line = None
            continue

        atx = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        heading: str | None = atx.group(1) if atx else None
        if heading is None and previous_line is not None and re.match(
            r"^\s{0,3}(?:=+|-+)\s*$", line
        ):
            heading = previous_line.strip()
        if heading is not None:
            explicit = re.findall(r"\{#([^}\s]+)", heading)
            if explicit:
                anchors.update(explicit)
            else:
                slug = _heading_slug(heading)
                if slug:
                    anchors.add(slug)
            previous_line = None
            continue
        previous_line = line if line.strip() else None

    return anchors


def _path_specs_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    if left.startswith(f"{right.rstrip('/')}/") or right.startswith(f"{left.rstrip('/')}/"):
        return True
    left_magic_index = min(
        (left.find(character) for character in "*?" if character in left),
        default=-1,
    )
    right_magic_index = min(
        (right.find(character) for character in "*?" if character in right),
        default=-1,
    )
    left_magic = left_magic_index >= 0
    right_magic = right_magic_index >= 0
    if left_magic and not right_magic:
        return bool(re.fullmatch(_glob_regex(left), right))
    if right_magic and not left_magic:
        return bool(re.fullmatch(_glob_regex(right), left))
    if not left_magic and not right_magic:
        return False

    # Exact glob intersection is expensive. A shared literal prefix is treated
    # conservatively as a possible overlap so parallel work cannot silently race.
    left_prefix = left[:left_magic_index]
    right_prefix = right[:right_magic_index]
    return left_prefix.startswith(right_prefix) or right_prefix.startswith(left_prefix)


def _glob_regex(pattern: str) -> str:
    """Translate repository globs to a conservative slash-aware regular expression."""

    pieces: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                if index + 2 < len(pattern) and pattern[index + 2] == "/":
                    pieces.append("(?:.*/)?")
                    index += 3
                else:
                    pieces.append(".*")
                    index += 2
            else:
                pieces.append("[^/]*")
                index += 1
        elif character == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(character))
            index += 1
    return "".join(pieces)


def _decision_ref_diagnostics(
    item: dict[str, Any], source: str, root: Path
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for reference in item.get("decision_refs", []):
        path_text, separator, anchor = reference.partition("#")
        if not _is_path_spec(path_text):
            diagnostics.append(
                Diagnostic("decision_ref.invalid", f"invalid repository path {path_text!r}", source)
            )
            continue
        path = root / path_text
        if not path.is_file():
            diagnostics.append(
                Diagnostic(
                    "decision_ref.missing",
                    f"referenced file does not exist: {path_text}",
                    source,
                )
            )
            continue
        if not separator:
            continue
        if not anchor:
            diagnostics.append(
                Diagnostic(
                    "decision_ref.anchor_missing",
                    f"heading anchor is empty: {reference}",
                    source,
                )
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            diagnostics.append(Diagnostic("decision_ref.unreadable", str(exc), source))
            continue
        if anchor not in _markdown_anchors(text):
            diagnostics.append(
                Diagnostic(
                    "decision_ref.anchor_missing",
                    f"heading anchor does not exist: {reference}",
                    source,
                )
            )
    return diagnostics


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


def _schema_sanity_error(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return "schema document must be an object"
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        return "root schema must be a closed object contract"
    if not CORE_SCHEMA_FIELDS.issubset(set(schema.get("required", []))):
        return "root schema is missing core required fields"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return "root schema properties must be an object"
    version = properties.get("schema_version")
    if not isinstance(version, dict) or version.get("const") != 1:
        return "schema_version must remain pinned to 1"
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return "schema must define local contracts in $defs"
    evidence = definitions.get("evidence")
    if not isinstance(evidence, dict) or not CORE_EVIDENCE_FIELDS.issubset(
        set(evidence.get("required", []))
    ):
        return "evidence schema is missing core required fields"

    def resolve_local_reference(reference: str) -> bool:
        if not reference.startswith("#/"):
            return False
        current: Any = schema
        for raw_part in reference[2:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return True

    pending: list[Any] = [schema]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and not resolve_local_reference(reference):
                return f"unresolvable or external schema reference: {reference}"
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return None


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


def _validate_backlog(root: Path = ROOT) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    items_dir = root / ITEMS_DIR
    schema_path = root / SCHEMA_PATH
    diagnostics: list[Diagnostic] = []
    items: dict[str, dict[str, Any]] = {}

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        sanity_error = _schema_sanity_error(schema)
        if sanity_error:
            raise SchemaError(sanity_error)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        return {}, [Diagnostic("schema.unavailable", str(exc), _relative(schema_path, root))]
    validator = Draft202012Validator(schema)

    for path in sorted(items_dir.glob("*.yml")):
        item, error = _read_mapping(path)
        source = _relative(path, root)
        if error:
            diagnostics.append(Diagnostic("yaml.invalid", error, source))
            continue
        assert item is not None
        try:
            schema_diagnostics = _schema_diagnostics(item, path, validator, root)
        except Exception as exc:  # fail closed on validator/reference implementation errors
            return {}, diagnostics + [
                Diagnostic(
                    "schema.unavailable",
                    f"schema evaluation failed: {exc}",
                    _relative(schema_path, root),
                )
            ]
        diagnostics.extend(schema_diagnostics)
        if schema_diagnostics:
            # Semantic checks assume the schema's nested mapping/list types. Keep a
            # malformed item out of the dependency graph instead of tracebacking.
            continue
        text_error = _text_contract_error(item)
        if text_error:
            diagnostics.append(Diagnostic("text.invalid", text_error, source))
            continue
        shape_error = _semantic_shape_error(item)
        if shape_error:
            diagnostics.append(Diagnostic("schema.contract_drift", shape_error, source))
            continue
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
        diagnostics.extend(_decision_ref_diagnostics(item, source, root))
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
            if not item["change_paths"]["write"]:
                diagnostics.append(
                    Diagnostic(
                        "path.write_missing",
                        f"status {status} requires at least one concrete write path",
                        source,
                    )
                )
            if status != "blocked" and item.get("decision_needed"):
                diagnostics.append(
                    Diagnostic(
                        "decision.unresolved",
                        f"status {status} requires decision_needed to be empty",
                        source,
                    )
                )
            if status != "blocked" and item.get("blocker") is not None:
                diagnostics.append(
                    Diagnostic(
                        "blocker.unresolved",
                        f"status {status} requires blocker to be null",
                        source,
                    )
                )
            for path_group in ("read", "write", "generated"):
                for value in item["change_paths"][path_group]:
                    if not _is_path_spec(value):
                        diagnostics.append(
                            Diagnostic(
                                "path.invalid",
                                f"ready-or-later change_paths.{path_group} value must be a "
                                f"repository-relative path or glob: {value!r}",
                                source,
                            )
                        )
        if status in LOCK_HOLDING_STATES and not item.get("branch"):
            diagnostics.append(
                Diagnostic("branch.missing", f"status {status} requires branch", source)
            )
        if status in LOCK_HOLDING_STATES and item.get("branch") and not _is_valid_short_branch(
            item["branch"]
        ):
            diagnostics.append(
                Diagnostic(
                    "branch.invalid",
                    "active branch must be a valid short Git branch name, not a refs/heads ref",
                    source,
                )
            )
        if status == "decision" and not item.get("decision_needed"):
            diagnostics.append(
                Diagnostic("decision.missing", "decision status requires decision_needed", source)
            )
        if status == "blocked" and not item.get("blocker"):
            diagnostics.append(
                Diagnostic("blocker.missing", "blocked status requires blocker", source)
            )
        if status in EVIDENCE_STATES:
            evidence = item.get("evidence", {})
            missing = [
                key
                for key in ("pr", "ci_runs", "last_known_good")
                if not evidence.get(key)
            ]
            if missing:
                diagnostics.append(
                    Diagnostic(
                        "evidence.missing",
                        f"status {status} requires evidence: {', '.join(missing)}",
                        source,
                    )
                )
            if item["verification"]["rendered_contract"] and not evidence.get(
                "rendered_artifacts"
            ):
                diagnostics.append(
                    Diagnostic(
                        "evidence.rendered_missing",
                        f"status {status} requires rendered artifacts for rendered_contract",
                        source,
                    )
                )
        if status in {"done", "rolled_back"} and not item["evidence"].get("post_merge"):
            diagnostics.append(
                Diagnostic(
                    "evidence.post_merge_missing",
                    f"status {status} requires post-merge verification evidence",
                    source,
                )
            )
        if status == "rolled_back":
            evidence = item["evidence"]
            for key in ("revert_ref", "follow_up"):
                if not evidence.get(key):
                    diagnostics.append(
                        Diagnostic(
                            "rollback.evidence_missing",
                            f"rolled_back status requires evidence.{key}",
                            source,
                        )
                    )
            follow_up = evidence.get("follow_up")
            if follow_up and (follow_up == identifier or follow_up not in items):
                diagnostics.append(
                    Diagnostic(
                        "rollback.follow_up_invalid",
                        f"follow-up work item must exist and differ from {identifier}: {follow_up}",
                        source,
                    )
                )
        if status == "cancelled" and not item.get("status_reason"):
            diagnostics.append(
                Diagnostic(
                    "status.reason_missing",
                    "cancelled status requires status_reason",
                    source,
                )
            )
        if status == "superseded":
            replacement = item.get("superseded_by")
            if not item.get("status_reason"):
                diagnostics.append(
                    Diagnostic(
                        "status.reason_missing",
                        "superseded status requires status_reason",
                        source,
                    )
                )
            if not replacement or replacement == identifier or replacement not in items:
                diagnostics.append(
                    Diagnostic(
                        "status.superseded_by_invalid",
                        "superseded status requires an existing, different superseded_by item",
                        source,
                    )
                )

    diagnostics.extend(_cycle_diagnostics(items))

    locks: dict[str, list[str]] = defaultdict(list)
    branches: dict[str, list[str]] = defaultdict(list)
    write_paths: list[tuple[str, str]] = []
    for identifier, item in items.items():
        if item.get("status") not in LOCK_HOLDING_STATES:
            continue
        branch = item.get("branch")
        if isinstance(branch, str):
            branches[branch].append(identifier)
        for lock in item.get("change_paths", {}).get("exclusive_locks", []):
            locks[lock].append(identifier)
        for path in item["change_paths"]["write"]:
            if _is_path_spec(path):
                write_paths.append((identifier, path))
    for lock, owners in sorted(locks.items()):
        if len(owners) > 1:
            diagnostics.append(
                Diagnostic(
                    "lock.conflict",
                    f"exclusive lock {lock!r} is active in {', '.join(sorted(owners))}",
                )
            )
    for branch, owners in sorted(branches.items()):
        if len(owners) > 1:
            diagnostics.append(
                Diagnostic(
                    "branch.conflict",
                    f"branch {branch!r} is active in {', '.join(sorted(owners))}",
                )
            )
    for index, (left_owner, left_path) in enumerate(write_paths):
        for right_owner, right_path in write_paths[index + 1 :]:
            if left_owner == right_owner or not _path_specs_overlap(left_path, right_path):
                continue
            diagnostics.append(
                Diagnostic(
                    "path.conflict",
                    f"write paths may overlap: {left_owner} {left_path!r}; "
                    f"{right_owner} {right_path!r}",
                )
            )

    return items, diagnostics


def validate_backlog(root: Path = ROOT) -> tuple[dict[str, dict[str, Any]], list[Diagnostic]]:
    """Validate fail-closed: malformed contracts must never bypass the gate via traceback."""

    try:
        return _validate_backlog(root)
    except Exception as exc:  # pragma: no cover - defensive boundary for contract drift
        return {}, [
            Diagnostic(
                "checker.failure",
                f"unexpected validation failure: {type(exc).__name__}: {exc}",
            )
        ]


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
