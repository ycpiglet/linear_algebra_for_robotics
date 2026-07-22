#!/usr/bin/env python3
"""Audit repository-owned figures and reproduce generated outputs fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
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
MANIFEST_PATH = Path("assets/artifact-manifest.yml")
SCHEMA_PATH = Path("platform/schemas/artifact-manifest.schema.json")
EXPECTED_INVENTORY_ROOTS = ("assets/figures",)
EXPECTED_CONSUMER_GLOBS = ("content/**/*.qmd", "courseware/labs/*.qmd")
DEBT_KEYS = (
    "missing_figure_id",
    "missing_caption",
    "missing_alt",
    "missing_provenance",
)
CORE_MANIFEST_FIELDS = {"schema_version", "scope", "legacy_baseline", "artifacts"}
CORE_ARTIFACT_FIELDS = {
    "id",
    "production",
    "sources",
    "generator",
    "output",
    "consumers",
    "license",
}
FIGURE_ID_RE = re.compile(r"^figure\.[a-z0-9]+(?:[.-][a-z0-9]+)*$")
DYNAMIC_SVG_ID_RE = re.compile(r"^[mp][0-9a-f]{8,}$")
IMAGE_RE = re.compile(
    r"!\[(?P<caption>(?:\\.|[^\]])*)\]"
    r"\(\s*(?P<target><[^>]+>|[^\s)]+)(?:\s+[^)]*)?\s*\)"
    r"(?:\s*\{(?P<attrs>[^}]*)\})?",
    flags=re.DOTALL,
)
FIGURE_ATTRIBUTE_RE = re.compile(r"(?:^|\s)#(?P<id>[A-Za-z][\w:.-]*)")
ALT_ATTRIBUTE_RE = re.compile(
    r"(?:^|\s)fig-alt\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    flags=re.DOTALL,
)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
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


@dataclass(frozen=True)
class FigureReference:
    consumer: str
    output: str
    caption: str
    alt: str | None
    figure_id: str | None

    @property
    def debt_identity(self) -> str:
        return f"{self.consumer}::{self.output}"


@dataclass(frozen=True)
class AuditResult:
    manifest: dict[str, Any] | None
    references: tuple[FigureReference, ...]
    debt: dict[str, tuple[str, ...]]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def ok(self) -> bool:
        return not self.diagnostics


@dataclass(frozen=True)
class RegeneratedArtifact:
    artifact_id: str
    output: str
    normalized_sha256: str


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.absolute().as_posix()


def _safe_repository_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "~")):
        return False
    if "\\" in value or "\x00" in value or any(character.isspace() for character in value):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _read_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return None, str(exc)
    if not isinstance(document, dict):
        return None, "document must be a YAML mapping"
    return document, None


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)


def _schema_sanity_error(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return "schema document must be an object"
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        return "root schema must be a closed object contract"
    required = schema.get("required")
    if not isinstance(required, list) or not CORE_MANIFEST_FIELDS.issubset(set(required)):
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
    artifact = definitions.get("artifact")
    if (
        not isinstance(artifact, dict)
        or artifact.get("additionalProperties") is not False
        or not CORE_ARTIFACT_FIELDS.issubset(set(artifact.get("required", [])))
    ):
        return "artifact schema is missing its closed core contract"

    def resolves(reference: str) -> bool:
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
            if isinstance(reference, str) and not resolves(reference):
                return f"unresolvable or external schema reference: {reference}"
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return None


def _manifest_shape_error(manifest: dict[str, Any]) -> str | None:
    if set(manifest) != CORE_MANIFEST_FIELDS or manifest.get("schema_version") != 1:
        return "root fields or schema_version violate the semantic contract"
    scope = manifest.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"inventory_roots", "consumer_globs"}:
        return "scope must contain only inventory_roots and consumer_globs"
    baseline = manifest.get("legacy_baseline")
    if not isinstance(baseline, dict) or set(baseline) != {"id", "captured_on", "debt"}:
        return "legacy_baseline has an invalid semantic shape"
    debt = baseline.get("debt")
    if not isinstance(debt, dict) or set(debt) != set(DEBT_KEYS):
        return "legacy_baseline.debt must contain every fixed debt category"
    if not all(isinstance(debt[key], list) for key in DEBT_KEYS):
        return "legacy baseline debt categories must be lists"
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return "artifacts must be a non-empty list"
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != CORE_ARTIFACT_FIELDS:
            return "each artifact must contain exactly the core artifact fields"
    return None


def _visible_markdown(text: str) -> str:
    """Remove fenced code and comments before discovering real figure consumers."""

    visible: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        if fence_character is not None:
            closing = re.match(r"^\s{0,3}(`{3,}|~{3,})\s*$", line.rstrip("\r\n"))
            if closing:
                marker = closing.group(1)
                if marker[0] == fence_character and len(marker) >= fence_length:
                    fence_character = None
                    fence_length = 0
            visible.append("\n" if line.endswith("\n") else "")
            continue
        opening = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if opening:
            marker = opening.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            visible.append("\n" if line.endswith("\n") else "")
            continue
        visible.append(line)
    return re.sub(r"<!--.*?-->", "", "".join(visible), flags=re.DOTALL)


def _consumer_paths(root: Path, globs: tuple[str, ...]) -> list[Path]:
    paths: set[Path] = set()
    for pattern in globs:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths)


def _discover_references(
    root: Path, outputs: set[str]
) -> tuple[list[FigureReference], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    references: list[FigureReference] = []
    inventory_root = (root / EXPECTED_INVENTORY_ROOTS[0]).resolve()
    for consumer_path in _consumer_paths(root, EXPECTED_CONSUMER_GLOBS):
        consumer = _relative(consumer_path, root)
        try:
            text = _visible_markdown(consumer_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            diagnostics.append(Diagnostic("consumer.unreadable", str(exc), consumer))
            continue
        for match in IMAGE_RE.finditer(text):
            raw_target = match.group("target").strip("<>")
            if re.match(r"^[a-z][a-z0-9+.-]*://", raw_target, flags=re.IGNORECASE):
                continue
            target_path = raw_target.split("#", 1)[0].split("?", 1)[0]
            resolved = (consumer_path.parent / target_path).resolve()
            try:
                resolved.relative_to(inventory_root)
            except ValueError:
                continue
            output = _relative(resolved, root)
            attributes = match.group("attrs") or ""
            figure_match = FIGURE_ATTRIBUTE_RE.search(attributes)
            alt_match = ALT_ATTRIBUTE_RE.search(attributes)
            references.append(
                FigureReference(
                    consumer=consumer,
                    output=output,
                    caption=match.group("caption").strip(),
                    alt=alt_match.group("value").strip() if alt_match else None,
                    figure_id=figure_match.group("id") if figure_match else None,
                )
            )
            if output not in outputs:
                diagnostics.append(
                    Diagnostic(
                        "consumer.unmanifested",
                        f"figure reference points to an output absent from the manifest: {output}",
                        consumer,
                    )
                )
    return references, diagnostics


def _inventory_files(root: Path) -> set[str]:
    files: set[str] = set()
    for relative_root in EXPECTED_INVENTORY_ROOTS:
        path = root / relative_root
        if path.is_dir():
            files.update(
                _relative(candidate, root) for candidate in path.rglob("*") if candidate.is_file()
            )
    return files


def _semantic_diagnostics(manifest: dict[str, Any], root: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    source = MANIFEST_PATH.as_posix()
    scope = manifest["scope"]
    if tuple(scope["inventory_roots"]) != EXPECTED_INVENTORY_ROOTS:
        diagnostics.append(
            Diagnostic(
                "scope.drift",
                f"inventory_roots must remain {list(EXPECTED_INVENTORY_ROOTS)!r}",
                source,
            )
        )
    if tuple(scope["consumer_globs"]) != EXPECTED_CONSUMER_GLOBS:
        diagnostics.append(
            Diagnostic(
                "scope.drift",
                f"consumer_globs must remain {list(EXPECTED_CONSUMER_GLOBS)!r}",
                source,
            )
        )

    debt = manifest["legacy_baseline"]["debt"]
    for key in DEBT_KEYS:
        if debt[key] != sorted(debt[key]):
            diagnostics.append(
                Diagnostic("baseline.nondeterministic", f"debt.{key} must be sorted", source)
            )

    identifiers: set[str] = set()
    outputs: set[str] = set()
    for index, artifact in enumerate(manifest["artifacts"]):
        artifact_source = f"{source}:artifacts[{index}]"
        identifier = artifact["id"]
        output = artifact["output"]
        if identifier in identifiers:
            diagnostics.append(
                Diagnostic("id.duplicate", f"duplicate stable ID {identifier}", artifact_source)
            )
        identifiers.add(identifier)
        if output in outputs:
            diagnostics.append(
                Diagnostic("output.duplicate", f"duplicate output {output}", artifact_source)
            )
        outputs.add(output)
        if not FIGURE_ID_RE.fullmatch(identifier):
            diagnostics.append(
                Diagnostic("id.invalid", f"invalid stable ID {identifier!r}", artifact_source)
            )

        paths = [output, *artifact["sources"], *artifact["consumers"]]
        paths.extend([artifact["license"]["basis"]])
        generator = artifact["generator"]
        if isinstance(generator, dict):
            paths.append(generator["lockfile"])
            paths.extend(generator["command"][1:])
        for value in paths:
            if not _safe_repository_path(value):
                diagnostics.append(
                    Diagnostic("path.invalid", f"unsafe repository path {value!r}", artifact_source)
                )

        if not output.startswith(f"{EXPECTED_INVENTORY_ROOTS[0]}/"):
            diagnostics.append(
                Diagnostic(
                    "output.out_of_scope",
                    f"output is outside assets/figures: {output}",
                    artifact_source,
                )
            )
        for value in [output, *artifact["sources"], *artifact["consumers"]]:
            path = root / value
            if not path.is_file():
                diagnostics.append(
                    Diagnostic(
                        "path.missing", f"required file does not exist: {value}", artifact_source
                    )
                )
            elif _relative(path, root) != value:
                diagnostics.append(
                    Diagnostic(
                        "path.escape",
                        f"path resolves outside or aliases its declared path: {value}",
                        artifact_source,
                    )
                )

        license_basis = artifact["license"]["basis"]
        basis_path = root / license_basis
        if not basis_path.is_file():
            diagnostics.append(
                Diagnostic(
                    "license.basis_missing",
                    f"license basis does not exist: {license_basis}",
                    artifact_source,
                )
            )
        else:
            try:
                basis_text = basis_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                diagnostics.append(
                    Diagnostic("license.basis_unreadable", str(exc), artifact_source)
                )
            else:
                if artifact["license"]["spdx"] not in basis_text:
                    diagnostics.append(
                        Diagnostic(
                            "license.unconfirmed",
                            f"{license_basis} does not contain {artifact['license']['spdx']}",
                            artifact_source,
                        )
                    )

        if artifact["production"] == "manual":
            if generator is not None:
                diagnostics.append(
                    Diagnostic(
                        "production.manual_generator",
                        "manual artifact must not claim a generator",
                        artifact_source,
                    )
                )
            if artifact["sources"] != [output]:
                diagnostics.append(
                    Diagnostic(
                        "production.manual_source",
                        "manual artifact source must be its hand-authored output path",
                        artifact_source,
                    )
                )
        else:
            if not isinstance(generator, dict):
                diagnostics.append(
                    Diagnostic(
                        "provenance.generator_missing",
                        "generated artifact requires a generator",
                        artifact_source,
                    )
                )
            else:
                command = generator["command"]
                if command[0] != "python" or command[1] not in artifact["sources"]:
                    diagnostics.append(
                        Diagnostic(
                            "provenance.generator_invalid",
                            "generator command must invoke a declared Python source",
                            artifact_source,
                        )
                    )
                if generator["lockfile"] != "uv.lock":
                    diagnostics.append(
                        Diagnostic(
                            "provenance.lockfile_invalid",
                            "generated artifacts must use uv.lock",
                            artifact_source,
                        )
                    )
                lockfile_path = root / generator["lockfile"]
                if not lockfile_path.is_file():
                    diagnostics.append(
                        Diagnostic(
                            "provenance.lockfile_missing",
                            f"generator lockfile does not exist: {generator['lockfile']}",
                            artifact_source,
                        )
                    )
                if not command[1].startswith("scripts/generate_") or not command[1].endswith(".py"):
                    diagnostics.append(
                        Diagnostic(
                            "provenance.generator_invalid",
                            f"unexpected generator path: {command[1]}",
                            artifact_source,
                        )
                    )
                if generator["normalizer"] != "svg-v1" or not output.endswith(".svg"):
                    diagnostics.append(
                        Diagnostic(
                            "provenance.normalizer_invalid",
                            "svg-v1 is required for generated SVG outputs",
                            artifact_source,
                        )
                    )
    inventory = _inventory_files(root)
    for missing in sorted(outputs - inventory):
        diagnostics.append(
            Diagnostic("inventory.missing", f"manifest output does not exist: {missing}", source)
        )
    for unmanifested in sorted(inventory - outputs):
        diagnostics.append(
            Diagnostic(
                "inventory.unmanifested", f"inventory file lacks provenance: {unmanifested}", source
            )
        )
    return diagnostics


def _reference_diagnostics(
    manifest: dict[str, Any],
    references: list[FigureReference],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    by_output: dict[str, list[FigureReference]] = defaultdict(list)
    for reference in references:
        by_output[reference.output].append(reference)
    for _output, output_references in sorted(by_output.items()):
        identities = Counter(reference.debt_identity for reference in output_references)
        for identity, count in sorted(identities.items()):
            if count > 1:
                diagnostics.append(
                    Diagnostic(
                        "consumer.duplicate_reference",
                        f"manifest consumers are path-based but {identity} occurs {count} times",
                        identity.split("::", 1)[0],
                    )
                )

    for artifact in manifest["artifacts"]:
        output = artifact["output"]
        expected = set(artifact["consumers"])
        actual = {reference.consumer for reference in by_output.get(output, [])}
        for missing in sorted(expected - actual):
            diagnostics.append(
                Diagnostic(
                    "consumer.reference_missing",
                    f"declared consumer does not reference {output}",
                    missing,
                )
            )
        for undeclared in sorted(actual - expected):
            diagnostics.append(
                Diagnostic(
                    "consumer.undeclared",
                    f"consumer references {output} but is absent from the manifest",
                    undeclared,
                )
            )
    return diagnostics


def _actual_debt(
    manifest: dict[str, Any],
    references: list[FigureReference],
    root: Path,
) -> dict[str, tuple[str, ...]]:
    debt: dict[str, set[str]] = {key: set() for key in DEBT_KEYS}
    for reference in references:
        identity = reference.debt_identity
        if not reference.figure_id:
            debt["missing_figure_id"].add(identity)
        if not reference.caption:
            debt["missing_caption"].add(identity)
        if not reference.alt:
            debt["missing_alt"].add(identity)
    manifested = {artifact["output"] for artifact in manifest["artifacts"]}
    debt["missing_provenance"].update(_inventory_files(root) - manifested)
    return {key: tuple(sorted(debt[key])) for key in DEBT_KEYS}


def _baseline_diagnostics(
    manifest: dict[str, Any],
    actual: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    baseline = manifest["legacy_baseline"]["debt"]
    for key in DEBT_KEYS:
        expected = set(baseline[key])
        observed = set(actual[key])
        introduced = sorted(observed - expected)
        resolved = sorted(expected - observed)
        if introduced:
            diagnostics.append(
                Diagnostic(
                    "debt.regression",
                    f"new {key} debt exceeds the legacy baseline: {', '.join(introduced)}",
                    MANIFEST_PATH.as_posix(),
                )
            )
        if resolved:
            diagnostics.append(
                Diagnostic(
                    "baseline.stale",
                    f"remove resolved {key} debt from the baseline: {', '.join(resolved)}",
                    MANIFEST_PATH.as_posix(),
                )
            )
    return diagnostics


def audit_repository(root: Path = ROOT) -> AuditResult:
    root = root.resolve()
    schema_path = root / SCHEMA_PATH
    manifest_path = root / MANIFEST_PATH
    try:
        schema = _read_schema(schema_path)
        Draft202012Validator.check_schema(schema)
        sanity_error = _schema_sanity_error(schema)
        if sanity_error:
            raise SchemaError(sanity_error)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, SchemaError) as exc:
        diagnostic = Diagnostic("schema.unavailable", str(exc), _relative(schema_path, root))
        return AuditResult(None, (), {key: () for key in DEBT_KEYS}, (diagnostic,))

    manifest, manifest_error = _read_manifest(manifest_path)
    if manifest_error or manifest is None:
        diagnostic = Diagnostic(
            "manifest.invalid",
            manifest_error or "manifest is unavailable",
            _relative(manifest_path, root),
        )
        return AuditResult(None, (), {key: () for key in DEBT_KEYS}, (diagnostic,))

    validator = Draft202012Validator(schema)
    schema_diagnostics = [
        Diagnostic(
            "schema.invalid",
            f"{'.'.join(str(part) for part in error.path) or '$'}: {error.message}",
            _relative(manifest_path, root),
        )
        for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    ]
    if schema_diagnostics:
        return AuditResult(manifest, (), {key: () for key in DEBT_KEYS}, tuple(schema_diagnostics))
    shape_error = _manifest_shape_error(manifest)
    if shape_error:
        diagnostic = Diagnostic(
            "schema.contract_drift", shape_error, _relative(manifest_path, root)
        )
        return AuditResult(manifest, (), {key: () for key in DEBT_KEYS}, (diagnostic,))

    diagnostics = _semantic_diagnostics(manifest, root)
    outputs = {artifact["output"] for artifact in manifest["artifacts"]}
    references, discovery_diagnostics = _discover_references(root, outputs)
    diagnostics.extend(discovery_diagnostics)
    diagnostics.extend(_reference_diagnostics(manifest, references))
    debt = _actual_debt(manifest, references, root)
    diagnostics.extend(_baseline_diagnostics(manifest, debt))
    ordered = tuple(
        sorted(diagnostics, key=lambda item: (item.source or "", item.code, item.message))
    )
    return AuditResult(manifest, tuple(references), debt, ordered)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_svg(data: bytes) -> bytes:
    """Remove volatile metadata and canonicalize Matplotlib's random internal IDs."""

    root = ET.fromstring(data)
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] == "metadata":
                parent.remove(child)

    replacements: dict[str, str] = {}
    for element in root.iter():
        identifier = element.attrib.get("id")
        if identifier and DYNAMIC_SVG_ID_RE.fullmatch(identifier):
            replacements.setdefault(identifier, f"generated-id-{len(replacements) + 1:04d}")
    for element in root.iter():
        for attribute, value in list(element.attrib.items()):
            for old, new in replacements.items():
                value = value.replace(f"#{old}", f"#{new}")
            # Matplotlib wraps long path attributes with indentation spaces. Those
            # bytes are formatting noise, not geometry, so compare canonical XML
            # whitespace while retaining every path token and coordinate.
            value = " ".join(value.split())
            if element.attrib.get(attribute) != value:
                element.set(attribute, value)
        identifier = element.attrib.get("id")
        if identifier in replacements:
            element.set("id", replacements[identifier])

    serialized = ET.tostring(root, encoding="unicode")
    canonical = ET.canonicalize(xml_data=serialized, strip_text=False)
    return canonical.encode("utf-8")


def _normalized_output(path: Path, normalizer: str) -> bytes:
    data = path.read_bytes()
    if normalizer != "svg-v1":
        raise ValueError(f"unsupported normalizer: {normalizer}")
    return _normalize_svg(data)


def build_report(root: Path = ROOT, audit: AuditResult | None = None) -> dict[str, Any]:
    root = root.resolve()
    audit = audit or audit_repository(root)
    if not audit.ok or audit.manifest is None:
        raise ValueError("artifact inventory is invalid; run the check command first")
    references_by_output: dict[str, list[FigureReference]] = defaultdict(list)
    for reference in audit.references:
        references_by_output[reference.output].append(reference)

    records: list[dict[str, Any]] = []
    for artifact in sorted(audit.manifest["artifacts"], key=lambda item: item["id"]):
        output_path = root / artifact["output"]
        record = {
            "id": artifact["id"],
            "production": artifact["production"],
            "sources": list(artifact["sources"]),
            "generator": artifact["generator"],
            "output": artifact["output"],
            "output_sha256": _sha256(output_path.read_bytes()),
            "consumers": [
                {
                    "path": reference.consumer,
                    "figure_id": reference.figure_id,
                    "caption_present": bool(reference.caption),
                    "alt_present": bool(reference.alt),
                }
                for reference in sorted(
                    references_by_output[artifact["output"]],
                    key=lambda item: (item.consumer, item.figure_id or ""),
                )
            ],
            "license": artifact["license"],
        }
        if artifact["generator"] is not None:
            record["normalized_sha256"] = _sha256(
                _normalized_output(output_path, artifact["generator"]["normalizer"])
            )
        records.append(record)

    generated = sum(record["production"] == "generated" for record in records)
    manual = sum(record["production"] == "manual" for record in records)
    return {
        "schema_version": 1,
        "manifest": MANIFEST_PATH.as_posix(),
        "legacy_baseline": audit.manifest["legacy_baseline"]["id"],
        "summary": {
            "artifacts": len(records),
            "generated": generated,
            "manual": manual,
            "references": len(audit.references),
            "consumer_files": len({reference.consumer for reference in audit.references}),
            "debt": {key: len(audit.debt[key]) for key in DEBT_KEYS},
        },
        "artifacts": records,
    }


def trace_artifact(identifier: str, root: Path = ROOT) -> dict[str, Any]:
    report = build_report(root)
    for artifact in report["artifacts"]:
        if artifact["id"] == identifier:
            return artifact
    raise KeyError(identifier)


def regenerate_repository(
    root: Path = ROOT,
    *,
    python_executable: str = sys.executable,
) -> tuple[tuple[RegeneratedArtifact, ...], tuple[Diagnostic, ...]]:
    root = root.resolve()
    audit = audit_repository(root)
    if not audit.ok or audit.manifest is None:
        return (), audit.diagnostics
    generated = sorted(
        (
            artifact
            for artifact in audit.manifest["artifacts"]
            if artifact["production"] == "generated"
        ),
        key=lambda item: item["id"],
    )
    diagnostics: list[Diagnostic] = []
    results: list[RegeneratedArtifact] = []
    with tempfile.TemporaryDirectory(prefix="atlas-artifact-regeneration-") as temporary:
        temporary_root = Path(temporary)
        for artifact in generated:
            for relative in [*artifact["sources"], artifact["generator"]["lockfile"]]:
                source = root / relative
                destination = temporary_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            (temporary_root / artifact["output"]).parent.mkdir(parents=True, exist_ok=True)

        matplotlib_config = temporary_root / ".matplotlib"
        matplotlib_config.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "LC_ALL": "C.UTF-8",
                "MPLCONFIGDIR": str(matplotlib_config),
                "PYTHONHASHSEED": "0",
                "SOURCE_DATE_EPOCH": "0",
                "TZ": "UTC",
            }
        )
        for artifact in generated:
            command = [python_executable, artifact["generator"]["command"][1]]
            before_outputs = {
                path: (temporary_root / path).read_bytes()
                for path in _inventory_files(temporary_root)
            }
            try:
                completed = subprocess.run(
                    command,
                    cwd=temporary_root,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                diagnostics.append(
                    Diagnostic(
                        "regeneration.timeout",
                        "generator exceeded the 120 second limit",
                        artifact["generator"]["command"][1],
                    )
                )
                continue
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()[-1200:]
                diagnostics.append(
                    Diagnostic(
                        "regeneration.failed",
                        f"generator exited {completed.returncode}: {detail}",
                        artifact["generator"]["command"][1],
                    )
                )
                continue
            after_outputs = {
                path: (temporary_root / path).read_bytes()
                for path in _inventory_files(temporary_root)
            }
            expected_output = artifact["output"]
            unexpected = sorted(set(after_outputs) - set(before_outputs) - {expected_output})
            modified_other = sorted(
                path
                for path in set(before_outputs) & set(after_outputs)
                if path != expected_output and before_outputs[path] != after_outputs[path]
            )
            if unexpected or modified_other:
                diagnostics.append(
                    Diagnostic(
                        "regeneration.unexpected_output",
                        "generator wrote outside its declared output: "
                        + ", ".join([*unexpected, *modified_other]),
                        artifact["generator"]["command"][1],
                    )
                )
                continue
            temporary_output = temporary_root / artifact["output"]
            if not temporary_output.is_file():
                diagnostics.append(
                    Diagnostic(
                        "regeneration.output_missing",
                        f"generator did not create {artifact['output']}",
                        artifact["generator"]["command"][1],
                    )
                )
                continue
            try:
                expected = _normalized_output(
                    root / artifact["output"], artifact["generator"]["normalizer"]
                )
                actual = _normalized_output(temporary_output, artifact["generator"]["normalizer"])
            except (OSError, ET.ParseError, ValueError) as exc:
                diagnostics.append(
                    Diagnostic("regeneration.normalization_failed", str(exc), artifact["output"])
                )
                continue
            if actual != expected:
                diagnostics.append(
                    Diagnostic(
                        "regeneration.drift",
                        f"normalized SHA256 {_sha256(expected)} != regenerated {_sha256(actual)}",
                        artifact["output"],
                    )
                )
                continue
            results.append(
                RegeneratedArtifact(
                    artifact_id=artifact["id"],
                    output=artifact["output"],
                    normalized_sha256=_sha256(actual),
                )
            )
    ordered_diagnostics = tuple(
        sorted(diagnostics, key=lambda item: (item.source or "", item.code, item.message))
    )
    return tuple(results), ordered_diagnostics


def _print_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        print(diagnostic, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate inventory, consumers, and debt baseline")
    subparsers.add_parser("report", help="emit deterministic JSON provenance report")
    trace_parser = subparsers.add_parser("trace", help="trace one stable artifact ID")
    trace_parser.add_argument("artifact_id")
    subparsers.add_parser("regenerate", help="regenerate generated artifacts in a temp root")
    arguments = parser.parse_args(argv)

    if arguments.command == "regenerate":
        results, diagnostics = regenerate_repository(arguments.root)
        if diagnostics:
            _print_diagnostics(diagnostics)
            return 1
        for result in results:
            print(
                f"{result.artifact_id}: {result.output} "
                f"normalized_sha256={result.normalized_sha256}"
            )
        print(f"artifact regeneration: {len(results)} generated output(s) match")
        return 0

    audit = audit_repository(arguments.root)
    if not audit.ok:
        _print_diagnostics(audit.diagnostics)
        return 1
    report = build_report(arguments.root, audit)
    if arguments.command == "check":
        summary = report["summary"]
        print(
            "artifact inventory: "
            f"{summary['artifacts']} total, {summary['generated']} generated, "
            f"{summary['manual']} manual, {summary['references']} reference(s), "
            f"legacy debt={sum(summary['debt'].values())}"
        )
        return 0
    if arguments.command == "trace":
        try:
            record = next(
                artifact
                for artifact in report["artifacts"]
                if artifact["id"] == arguments.artifact_id
            )
        except StopIteration:
            print(f"unknown artifact ID: {arguments.artifact_id}", file=sys.stderr)
            return 2
        print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
