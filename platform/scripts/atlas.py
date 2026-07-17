#!/usr/bin/env python3
"""Validate and compile the Knowledge Atlas content graph.

The compiler intentionally keeps content authoring separate from the web UI.  It
reads Quarto YAML front matter, validates the public metadata contract, checks
the semantic graphs, and emits deterministic JSON that a static site can use.

Run from any directory:

    python platform/scripts/atlas.py validate
    python platform/scripts/atlas.py build
    python platform/scripts/atlas.py build --check
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised only in an incomplete env
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - exercised only in an incomplete env
    raise SystemExit("jsonschema is required: python -m pip install jsonschema") from exc


SCHEMA_VERSION = "1.0.0"
UTC = timezone.utc  # noqa: UP017 -- keep the content compiler usable with Python 3.10/3.11.
DEPTH_ORDER = [
    "intuition",
    "application",
    "analysis",
    "implementation",
    "derivation",
    "proof",
    "teaching",
]
CONTENT_DIRS = {
    "concept": Path("content/concepts"),
    "proof": Path("content/proofs"),
    "path": Path("content/paths"),
}
SCHEMA_FILES = {
    "concept": "concept.schema.json",
    "proof": "proof.schema.json",
    "path": "path.schema.json",
}
RELATION_KEYS = [
    "requires",
    "helpful",
    "derived_from",
    "deepens",
    "contrasts_with",
    "same_structure_as",
    "used_in",
]
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    source: str | None = None
    pointer: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.source:
            result["source"] = self.source
        if self.pointer:
            result["pointer"] = self.pointer
        return result


@dataclass
class Document:
    kind: str
    path: Path
    source: str
    metadata: dict[str, Any]

    @property
    def identifier(self) -> str | None:
        value = self.metadata.get("id")
        return value if isinstance(value, str) else None


@dataclass
class AtlasProject:
    root: Path
    documents: list[Document] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def documents_of_kind(self, kind: str) -> list[Document]:
        return [document for document in self.documents if document.kind == kind]

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "warning"]


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def read_front_matter(path: Path) -> dict[str, Any]:
    """Read YAML front matter without interpreting the Markdown body."""

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("file must start with a YAML front-matter delimiter (`---`)")

    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in {"---", "..."}:
            closing = index
            break
    if closing is None:
        raise ValueError("front matter has no closing delimiter (`---` or `...`)")

    parsed = yaml.safe_load("\n".join(lines[1:closing]))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("front matter must be a YAML mapping")
    return parsed


def _listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_prerequisite(value: Any, default_competency: str) -> Any:
    if isinstance(value, str):
        return {"concept": value, "competency": default_competency}
    if isinstance(value, dict):
        normalized = copy.deepcopy(value)
        if "id" in normalized and "concept" not in normalized:
            normalized["concept"] = normalized.pop("id")
        normalized.setdefault("competency", default_competency)
        competency_aliases = {
            "intuition": "explain",
            "application": "apply",
            "analysis": "calculate",
            "implementation": "apply",
            "derivation": "derive",
            "proof": "prove",
            "teaching": "teach",
        }
        competency = normalized.get("competency")
        if isinstance(competency, str):
            normalized["competency"] = competency_aliases.get(competency, competency)
        return normalized
    return value


def _normalize_prerequisite_groups(prerequisites: Any) -> Any:
    if prerequisites is None:
        return {}
    if not isinstance(prerequisites, dict):
        return prerequisites

    canonical_prerequisites: dict[str, Any] = {}
    for depth, group in prerequisites.items():
        if isinstance(group, list):
            group = {"required": group}
        if not isinstance(group, dict):
            canonical_prerequisites[depth] = group
            continue
        group = copy.deepcopy(group)
        if "not-required" in group and "not_required" not in group:
            group["not_required"] = group.pop("not-required")
        canonical_group: dict[str, Any] = {}
        for category, default_competency in (
            ("required", "explain"),
            ("helpful", "recognize"),
            ("not_required", "recognize"),
        ):
            canonical_group[category] = [
                _normalize_prerequisite(item, default_competency)
                for item in _listify(group.get(category))
            ]
        for key, value in group.items():
            if key not in canonical_group:
                canonical_group[key] = value
        canonical_prerequisites[str(depth).replace("-", "_")] = canonical_group
    return canonical_prerequisites


def normalize_metadata(kind: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Convert supported authoring shorthands to the canonical manifest shape."""

    normalized = copy.deepcopy(dict(metadata))
    if "one-line" in normalized and "one_line" not in normalized:
        normalized["one_line"] = normalized.pop("one-line")
    if "reading-time" in normalized and "reading_time" not in normalized:
        normalized["reading_time"] = normalized.pop("reading-time")
    if "estimated-time" in normalized and "estimated_time" not in normalized:
        normalized["estimated_time"] = normalized.pop("estimated-time")
    if "entry-points" in normalized and "entry_points" not in normalized:
        normalized["entry_points"] = normalized.pop("entry-points")
    if "entry-concepts" in normalized and "entry_concepts" not in normalized:
        normalized["entry_concepts"] = normalized.pop("entry-concepts")
    if "exit-concept" in normalized and "exit_concept" not in normalized:
        normalized["exit_concept"] = normalized.pop("exit-concept")
    if "page-url" in normalized and "page_url" not in normalized:
        normalized["page_url"] = normalized.pop("page-url")

    if kind == "concept":
        normalized["prerequisites"] = _normalize_prerequisite_groups(
            normalized.get("prerequisites")
        )

        relations = normalized.get("relations")
        if relations is None:
            normalized["relations"] = {}
        elif isinstance(relations, dict):
            canonical_relations: dict[str, Any] = {}
            for relation, targets in relations.items():
                canonical_relations[str(relation).replace("-", "_")] = _listify(targets)
            normalized["relations"] = canonical_relations
        normalized.setdefault("aliases", [])

    elif kind == "proof":
        if "depends_on" in normalized and "dependencies" not in normalized:
            normalized["dependencies"] = normalized.pop("depends_on")
        if "applies_to" in normalized and "concepts" not in normalized:
            normalized["concepts"] = normalized.pop("applies_to")
        if "proves" in normalized and "concepts" not in normalized:
            normalized["concepts"] = normalized.pop("proves")
        normalized["dependencies"] = _listify(normalized.get("dependencies"))
        normalized["concepts"] = _listify(normalized.get("concepts"))
        normalized["assumptions"] = _listify(normalized.get("assumptions"))
        normalized["prerequisites"] = _normalize_prerequisite_groups(
            normalized.get("prerequisites")
        )

    elif kind == "path":
        def normalize_step(step: Any) -> Any:
            if isinstance(step, str):
                return {"concept": step, "depth": "intuition", "optional": False}
            if isinstance(step, dict):
                result = copy.deepcopy(step)
                if "id" in result and "concept" not in result:
                    result["concept"] = result.pop("id")
                if "level" in result and "depth" not in result:
                    result["depth"] = result.pop("level")
                result.setdefault("depth", "intuition")
                result.setdefault("optional", False)
                return result
            return step

        if "steps" in normalized:
            normalized["steps"] = [normalize_step(step) for step in _listify(normalized["steps"])]
        if "stages" in normalized and isinstance(normalized["stages"], list):
            stages = []
            for stage in normalized["stages"]:
                if not isinstance(stage, dict):
                    stages.append(stage)
                    continue
                canonical_stage = copy.deepcopy(stage)
                canonical_stage["steps"] = [
                    normalize_step(step) for step in _listify(canonical_stage.get("steps"))
                ]
                stages.append(canonical_stage)
            normalized["stages"] = stages
        if "steps" not in normalized and "stages" not in normalized:
            inferred = _listify(normalized.get("entry_concepts"))
            exit_concept = normalized.get("exit_concept")
            if isinstance(exit_concept, str) and exit_concept not in inferred:
                inferred.append(exit_concept)
            if inferred:
                normalized["steps"] = [normalize_step(step) for step in inferred]

    return normalized


def _load_validators() -> dict[str, Draft202012Validator]:
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"
    validators: dict[str, Draft202012Validator] = {}
    for kind, filename in SCHEMA_FILES.items():
        schema = json.loads((schema_dir / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[kind] = Draft202012Validator(schema)
    return validators


def discover_documents(root: Path) -> AtlasProject:
    root = root.resolve()
    project = AtlasProject(root=root)
    validators = _load_validators()

    for kind, relative_directory in CONTENT_DIRS.items():
        directory = root / relative_directory
        if not directory.exists():
            continue
        paths = sorted(
            [*directory.rglob("*.qmd"), *directory.rglob("*.md")],
            key=lambda item: item.as_posix(),
        )
        for path in paths:
            source = _repo_relative(path, root)
            try:
                raw_metadata = read_front_matter(path)
            except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                project.diagnostics.append(
                    Diagnostic("error", "frontmatter.invalid", str(exc), source)
                )
                continue

            metadata = normalize_metadata(kind, raw_metadata)
            document = Document(kind=kind, path=path, source=source, metadata=metadata)
            project.documents.append(document)
            validation_errors = sorted(
                validators[kind].iter_errors(metadata),
                key=lambda error: list(error.absolute_path),
            )
            for error in validation_errors:
                pointer = "/" + "/".join(str(part) for part in error.absolute_path)
                project.diagnostics.append(
                    Diagnostic(
                        "error",
                        f"schema.{kind}",
                        error.message,
                        source,
                        pointer if pointer != "/" else None,
                    )
                )

    validate_semantics(project)
    project.diagnostics.sort(
        key=lambda item: (
            item.source or "",
            item.pointer or "",
            item.severity,
            item.code,
            item.message,
        )
    )
    return project


def _index_documents(
    documents: Sequence[Document], kind: str, diagnostics: list[Diagnostic]
) -> dict[str, Document]:
    index: dict[str, Document] = {}
    for document in documents:
        if document.kind != kind:
            continue
        identifier = document.identifier
        if identifier is None or not ID_RE.fullmatch(identifier):
            continue
        if identifier in index:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "id.duplicate",
                    f"duplicate {kind} id `{identifier}`; "
                    f"first declared in {index[identifier].source}",
                    document.source,
                    "/id",
                )
            )
            continue
        index[identifier] = document
    return index


def _strongly_connected_components(adjacency: Mapping[str, set[str]]) -> list[list[str]]:
    """Tarjan SCC, returning only graph components in deterministic order."""

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(adjacency.get(node, set())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))

    all_nodes = set(adjacency)
    for targets in adjacency.values():
        all_nodes.update(targets)
    for node in sorted(all_nodes):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda component: component[0] if component else "")


def _document_site_path(document: Document, root: Path) -> str:
    metadata = document.metadata
    explicit = metadata.get("page_url")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lstrip("/")

    # Quarto mirrors a website source path below the project root.  Keep the
    # leading ``content/`` segment so manifest-generated links point to the
    # same files Quarto actually renders.  Authors can still opt into a clean
    # route explicitly with ``page_url``.
    try:
        relative = document.path.resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(document.path.name)

    output_file = metadata.get("output-file")
    if isinstance(output_file, str) and output_file.strip():
        output_path = relative.parent / output_file.strip()
    else:
        output_path = relative.with_suffix(".html")
    return output_path.as_posix().lstrip("/")


def _path_stages(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "stages" in metadata and isinstance(metadata["stages"], list):
        return copy.deepcopy(metadata["stages"])
    return [
        {
            "id": "main",
            "title": metadata.get("title", "Main"),
            "steps": copy.deepcopy(metadata.get("steps", [])),
        }
    ]


def _iter_prerequisites(
    metadata: Mapping[str, Any],
) -> Iterator[tuple[str, str, int, dict[str, Any]]]:
    prerequisites = metadata.get("prerequisites", {})
    if not isinstance(prerequisites, dict):
        return
    for depth, group in prerequisites.items():
        if not isinstance(group, dict):
            continue
        for category in ("required", "helpful", "not_required"):
            for position, reference in enumerate(group.get(category, [])):
                if isinstance(reference, dict):
                    yield depth, category, position, reference


def validate_semantics(project: AtlasProject) -> None:
    diagnostics = project.diagnostics
    concepts = _index_documents(project.documents, "concept", diagnostics)
    proofs = _index_documents(project.documents, "proof", diagnostics)
    paths = _index_documents(project.documents, "path", diagnostics)

    global_ids: dict[str, Document] = {}
    for document in project.documents:
        identifier = document.identifier
        if identifier is None or not ID_RE.fullmatch(identifier):
            continue
        if identifier in global_ids and global_ids[identifier].kind != document.kind:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "id.cross_kind_collision",
                    f"`{identifier}` is already used by a {global_ids[identifier].kind}",
                    document.source,
                    "/id",
                )
            )
        else:
            global_ids[identifier] = document

    url_index: dict[str, Document] = {}
    for document in project.documents:
        site_path = _document_site_path(document, project.root)
        if site_path in url_index:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "url.collision",
                    f"output URL `{site_path}` is also produced by {url_index[site_path].source}",
                    document.source,
                )
            )
        else:
            url_index[site_path] = document

    prerequisite_graph: dict[str, set[str]] = {identifier: set() for identifier in concepts}
    for concept_id, document in concepts.items():
        metadata = document.metadata
        prerequisites = metadata.get("prerequisites", {})
        if isinstance(prerequisites, dict):
            for depth, group in prerequisites.items():
                if not isinstance(group, dict):
                    continue
                for category in ("required", "helpful", "not_required"):
                    for position, reference in enumerate(group.get(category, [])):
                        if not isinstance(reference, dict):
                            continue
                        target = reference.get("concept")
                        if not isinstance(target, str) or not ID_RE.fullmatch(target):
                            continue
                        pointer = f"/prerequisites/{depth}/{category}/{position}/concept"
                        if target == concept_id:
                            diagnostics.append(
                                Diagnostic(
                                    "error" if category == "required" else "warning",
                                    "prerequisite.self_reference",
                                    f"concept `{concept_id}` references itself as {category}",
                                    document.source,
                                    pointer,
                                )
                            )
                        if target not in concepts:
                            severity = "warning" if category == "not_required" else "error"
                            diagnostics.append(
                                Diagnostic(
                                    severity,
                                    "prerequisite.unresolved",
                                    f"{category} prerequisite `{target}` does not exist",
                                    document.source,
                                    pointer,
                                )
                            )
                        if category == "required" and target in concepts:
                            prerequisite_graph[concept_id].add(target)

        relations = metadata.get("relations", {})
        if isinstance(relations, dict):
            for relation, targets in relations.items():
                if not isinstance(targets, list):
                    continue
                for position, target in enumerate(targets):
                    if not isinstance(target, str) or not ID_RE.fullmatch(target):
                        continue
                    if target == concept_id:
                        diagnostics.append(
                            Diagnostic(
                                "warning",
                                "relation.self_reference",
                                f"concept `{concept_id}` relates to itself via `{relation}`",
                                document.source,
                                f"/relations/{relation}/{position}",
                            )
                        )
                    elif target not in concepts:
                        diagnostics.append(
                            Diagnostic(
                                "warning",
                                "relation.unresolved",
                                f"relation target `{target}` is planned but not yet present",
                                document.source,
                                f"/relations/{relation}/{position}",
                            )
                        )

    for component in _strongly_connected_components(prerequisite_graph):
        if len(component) > 1:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "prerequisite.cycle",
                    "required prerequisite cycle: " + " -> ".join(component + [component[0]]),
                )
            )

    proof_graph: dict[str, set[str]] = {identifier: set() for identifier in proofs}
    for proof_id, document in proofs.items():
        for position, dependency in enumerate(document.metadata.get("dependencies", [])):
            if not isinstance(dependency, str) or not ID_RE.fullmatch(dependency):
                continue
            if dependency == proof_id:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "proof.self_dependency",
                        f"proof `{proof_id}` depends on itself",
                        document.source,
                        f"/dependencies/{position}",
                    )
                )
            elif dependency not in proofs:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "proof.unresolved_dependency",
                        f"proof dependency `{dependency}` does not exist",
                        document.source,
                        f"/dependencies/{position}",
                    )
                )
            else:
                proof_graph[proof_id].add(dependency)
        for depth, category, position, reference in _iter_prerequisites(document.metadata):
            target = reference.get("concept")
            if not isinstance(target, str) or not ID_RE.fullmatch(target):
                continue
            pointer = f"/prerequisites/{depth}/{category}/{position}/concept"
            if target == proof_id:
                diagnostics.append(
                    Diagnostic(
                        "error" if category == "required" else "warning",
                        "proof.self_dependency",
                        f"proof `{proof_id}` depends on itself",
                        document.source,
                        pointer,
                    )
                )
            elif target in proofs:
                if category == "required":
                    proof_graph[proof_id].add(target)
            elif target not in concepts:
                severity = "warning" if category == "not_required" else "error"
                diagnostics.append(
                    Diagnostic(
                        severity,
                        "proof.unresolved_prerequisite",
                        f"proof prerequisite `{target}` does not exist",
                        document.source,
                        pointer,
                    )
                )
        for position, concept_id in enumerate(document.metadata.get("concepts", [])):
            if isinstance(concept_id, str) and concept_id not in concepts:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "proof.unresolved_concept",
                        f"proof concept `{concept_id}` does not exist",
                        document.source,
                        f"/concepts/{position}",
                    )
                )

    for component in _strongly_connected_components(proof_graph):
        if len(component) > 1:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "proof.cycle",
                    "proof dependency cycle: " + " -> ".join(component + [component[0]]),
                )
            )

    for _path_id, document in paths.items():
        entry_points = document.metadata.get("entry_points", {})
        if isinstance(entry_points, dict):
            for depth, concept_id in entry_points.items():
                if isinstance(concept_id, str) and concept_id not in concepts:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "path.unresolved_entry_point",
                            f"entry point concept `{concept_id}` does not exist",
                            document.source,
                            f"/entry_points/{depth}",
                        )
                    )
        for position, concept_id in enumerate(document.metadata.get("entry_concepts", [])):
            if isinstance(concept_id, str) and concept_id not in concepts:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "path.unresolved_entry_point",
                        f"entry concept `{concept_id}` does not exist",
                        document.source,
                        f"/entry_concepts/{position}",
                    )
                )
        exit_concept = document.metadata.get("exit_concept")
        if isinstance(exit_concept, str) and exit_concept not in concepts:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "path.unresolved_exit_concept",
                    f"exit concept `{exit_concept}` does not exist",
                    document.source,
                    "/exit_concept",
                )
            )
        seen: dict[tuple[str, str], int] = {}
        global_position = 0
        for stage_index, stage in enumerate(_path_stages(document.metadata)):
            if not isinstance(stage, dict):
                continue
            for step_index, step in enumerate(stage.get("steps", [])):
                global_position += 1
                if not isinstance(step, dict):
                    continue
                concept_id = step.get("concept")
                depth = step.get("depth", "intuition")
                if not isinstance(concept_id, str):
                    continue
                seen_key = (concept_id, str(depth))
                if concept_id not in concepts:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "path.unresolved_concept",
                            f"path step concept `{concept_id}` does not exist",
                            document.source,
                            f"/stages/{stage_index}/steps/{step_index}/concept",
                        )
                    )
                elif seen_key in seen:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "path.repeated_concept",
                            f"`{concept_id}` at depth `{depth}` appears at steps "
                            f"{seen[seen_key]} and {global_position}",
                            document.source,
                        )
                    )
                else:
                    seen[seen_key] = global_position


def _utc_timestamp() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        instant = datetime.fromtimestamp(int(source_date_epoch), tz=UTC)
    else:
        instant = datetime.now(tz=UTC)
    return instant.isoformat(timespec="seconds").replace("+00:00", "Z")


def _public_metadata(document: Document, keys: Iterable[str]) -> dict[str, Any]:
    return {key: copy.deepcopy(document.metadata[key]) for key in keys if key in document.metadata}


def _sorted_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True))


def build_manifest(project: AtlasProject, generated_at: str | None = None) -> dict[str, Any]:
    if project.errors:
        raise ValueError("cannot build manifest while validation errors exist")

    generated_at = generated_at or _utc_timestamp()
    concepts = {
        document.identifier: document
        for document in project.documents_of_kind("concept")
        if document.identifier is not None
    }
    proofs = {
        document.identifier: document
        for document in project.documents_of_kind("proof")
        if document.identifier is not None
    }
    path_documents = {
        document.identifier: document
        for document in project.documents_of_kind("path")
        if document.identifier is not None
    }

    backlinks: dict[str, dict[str, list[dict[str, Any]]]] = {
        concept_id: {
            "required_by": [],
            "helpful_for": [],
            "explicitly_not_required_by": [],
            "relations": [],
            "proofs": [],
            "required_by_proofs": [],
            "paths": [],
        }
        for concept_id in concepts
    }
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()

    for concept_id, document in concepts.items():
        site_path = _document_site_path(document, project.root)
        nodes[concept_id] = {
            "id": concept_id,
            "type": "concept",
            "label": document.metadata["title"],
            "domain": document.metadata["domain"],
            "url": "/" + site_path,
            "site_path": site_path,
        }

    def add_edge(edge_type: str, source: str, target: str, **attributes: Any) -> None:
        edge = {"type": edge_type, "source": source, "target": target, **attributes}
        identity_payload = json.dumps(
            edge, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(identity_payload.encode()).hexdigest()[:16]
        edge["id"] = f"{edge_type}:{digest}"
        if edge["id"] in edge_ids:
            return
        edge_ids.add(edge["id"])
        edges.append(edge)

    for concept_id, document in concepts.items():
        for depth in DEPTH_ORDER:
            group = document.metadata.get("prerequisites", {}).get(depth)
            if not isinstance(group, dict):
                continue
            for category, backlink_key in (
                ("required", "required_by"),
                ("helpful", "helpful_for"),
                ("not_required", "explicitly_not_required_by"),
            ):
                for reference in group.get(category, []):
                    target = reference["concept"]
                    record = {
                        "concept": concept_id,
                        "title": document.metadata["title"],
                        "depth": depth,
                        "competency": reference.get("competency"),
                        "reason": reference.get("reason"),
                        "diagnostic": reference.get("diagnostic"),
                        "url": "/" + _document_site_path(document, project.root),
                    }
                    record = {key: value for key, value in record.items() if value is not None}
                    if target in backlinks:
                        backlinks[target][backlink_key].append(record)
                    if target not in nodes:
                        nodes[target] = {
                            "id": target,
                            "type": "unresolved",
                            "label": target,
                            "resolved": False,
                        }
                    add_edge(
                        "prerequisite",
                        target,
                        concept_id,
                        category=category,
                        depth=depth,
                        competency=reference.get("competency"),
                        resolved=target in concepts,
                    )

        for relation in RELATION_KEYS:
            for target in document.metadata.get("relations", {}).get(relation, []):
                resolved = target in concepts
                if resolved:
                    backlinks[target]["relations"].append(
                        {
                            "concept": concept_id,
                            "title": document.metadata["title"],
                            "relation": relation,
                            "url": "/" + _document_site_path(document, project.root),
                        }
                    )
                elif target not in nodes:
                    nodes[target] = {
                        "id": target,
                        "type": "unresolved",
                        "label": target,
                        "resolved": False,
                    }
                add_edge("relation", concept_id, target, relation=relation, resolved=resolved)

    proof_entries: list[dict[str, Any]] = []
    for proof_id, document in sorted(proofs.items()):
        site_path = _document_site_path(document, project.root)
        entry = _public_metadata(
            document,
            [
                "id",
                "title",
                "domain",
                "one_line",
                "statement",
                "theorem",
                "difficulty",
                "status",
                "dependencies",
                "concepts",
                "prerequisites",
                "assumptions",
                "level",
            ],
        )
        entry.update({"source": document.source, "url": "/" + site_path, "site_path": site_path})
        proof_entries.append(entry)
        nodes[proof_id] = {
            "id": proof_id,
            "type": "proof",
            "label": document.metadata["title"],
            "url": "/" + site_path,
            "site_path": site_path,
        }
        for dependency in document.metadata.get("dependencies", []):
            add_edge("proof_dependency", dependency, proof_id, resolved=True)
        for depth, category, _, reference in _iter_prerequisites(document.metadata):
            target = reference["concept"]
            if target in proofs:
                add_edge(
                    "proof_dependency",
                    target,
                    proof_id,
                    category=category,
                    depth=depth,
                    competency=reference.get("competency"),
                    resolved=True,
                )
            elif target in concepts:
                backlinks[target]["required_by_proofs"].append(
                    {
                        "id": proof_id,
                        "title": document.metadata["title"],
                        "url": "/" + site_path,
                        "category": category,
                        "depth": depth,
                        "competency": reference.get("competency"),
                        "reason": reference.get("reason"),
                    }
                )
                add_edge(
                    "proof_prerequisite",
                    target,
                    proof_id,
                    category=category,
                    depth=depth,
                    competency=reference.get("competency"),
                    resolved=True,
                )
        for concept_id in document.metadata.get("concepts", []):
            backlinks[concept_id]["proofs"].append(
                {"id": proof_id, "title": document.metadata["title"], "url": "/" + site_path}
            )
            add_edge("proved_by", concept_id, proof_id, resolved=True)

    path_entries: list[dict[str, Any]] = []
    for path_id, document in sorted(path_documents.items()):
        site_path = _document_site_path(document, project.root)
        stages = _path_stages(document.metadata)
        flattened_steps: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        global_position = 0
        normalized_stages: list[dict[str, Any]] = []
        for stage_index, stage in enumerate(stages):
            stage_id = stage.get("id") or f"stage-{stage_index + 1}"
            normalized_stage = {
                "id": stage_id,
                "title": stage.get("title", f"Stage {stage_index + 1}"),
                "summary": stage.get("summary"),
                "steps": [],
            }
            normalized_stage = {
                key: value for key, value in normalized_stage.items() if value is not None
            }
            for stage_position, step in enumerate(stage.get("steps", []), start=1):
                global_position += 1
                normalized_step = copy.deepcopy(step)
                normalized_step.update(
                    {
                        "position": global_position,
                        "stage": stage_id,
                        "stage_position": stage_position,
                    }
                )
                normalized_stage["steps"].append(normalized_step)
                flattened_steps.append(normalized_step)
                concept_id = normalized_step["concept"]
                backlinks[concept_id]["paths"].append(
                    {
                        "id": path_id,
                        "title": document.metadata["title"],
                        "url": "/" + site_path,
                        "depth": normalized_step.get("depth", "intuition"),
                        "position": global_position,
                        "stage": stage_id,
                        "optional": normalized_step.get("optional", False),
                    }
                )
                if previous is not None:
                    add_edge(
                        "path_order",
                        previous["concept"],
                        concept_id,
                        path=path_id,
                        from_position=previous["position"],
                        to_position=global_position,
                    )
                previous = normalized_step
            normalized_stages.append(normalized_stage)

        entry = _public_metadata(
            document,
            [
                "id",
                "title",
                "aliases",
                "domain",
                "difficulty",
                "one_line",
                "summary",
                "goal",
                "audience",
                "estimated_time",
                "entry_points",
                "entry_concepts",
                "exit_concept",
                "status",
            ],
        )
        entry.update(
            {
                "source": document.source,
                "url": "/" + site_path,
                "site_path": site_path,
                "stages": normalized_stages,
                "steps": flattened_steps,
            }
        )
        path_entries.append(entry)

    concept_entries: list[dict[str, Any]] = []
    for concept_id, document in sorted(concepts.items()):
        site_path = _document_site_path(document, project.root)
        entry = _public_metadata(
            document,
            [
                "id",
                "title",
                "aliases",
                "domain",
                "one_line",
                "summary",
                "difficulty",
                "importance",
                "importance_note",
                "practice_frequency",
                "practice_frequency_note",
                "application_areas",
                "reading_time",
                "status",
                "prerequisites",
                "relations",
                "review",
                "tags",
            ],
        )
        normalized_backlinks = {
            key: _sorted_records(value) for key, value in backlinks[concept_id].items()
        }
        entry.update(
            {
                "source": document.source,
                "url": "/" + site_path,
                "site_path": site_path,
                "backlinks": normalized_backlinks,
            }
        )
        concept_entries.append(entry)

    edges.sort(key=lambda edge: edge["id"])
    node_entries = sorted(nodes.values(), key=lambda node: (node["type"], node["id"]))
    warning_entries = [item.as_dict() for item in project.warnings]
    alias_index: dict[str, list[str]] = {}
    for concept in concept_entries:
        for term in [concept["id"], concept["title"], *concept.get("aliases", [])]:
            key = str(term).casefold()
            alias_index.setdefault(key, []).append(concept["id"])
    alias_index = {key: sorted(set(value)) for key, value in sorted(alias_index.items())}

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "depth_order": DEPTH_ORDER,
        "counts": {
            "concepts": len(concept_entries),
            "proofs": len(proof_entries),
            "paths": len(path_entries),
            "warnings": len(warning_entries),
        },
        "concepts": concept_entries,
        "proofs": proof_entries,
        "paths": path_entries,
        "indexes": {
            "concepts": {item["id"]: index for index, item in enumerate(concept_entries)},
            "proofs": {item["id"]: index for index, item in enumerate(proof_entries)},
            "paths": {item["id"]: index for index, item in enumerate(path_entries)},
            "aliases": alias_index,
        },
        "graph": {"nodes": node_entries, "edges": edges},
        "diagnostics": {"warnings": warning_entries},
    }
    hashable = copy.deepcopy(manifest)
    hashable.pop("generated_at", None)
    manifest["content_hash"] = "sha256:" + hashlib.sha256(
        json.dumps(
            hashable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return manifest


def output_payloads(manifest: Mapping[str, Any]) -> dict[str, Any]:
    common = {
        "schema_version": manifest["schema_version"],
        "generated_at": manifest["generated_at"],
        "content_hash": manifest["content_hash"],
    }
    return {
        "concept-manifest.json": dict(manifest),
        "backlinks.json": {
            **common,
            "concepts": {item["id"]: item["backlinks"] for item in manifest["concepts"]},
        },
        "knowledge-graph.json": {**common, **manifest["graph"]},
        "paths.json": {**common, "paths": manifest["paths"]},
    }


def _serialized(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_outputs(output_directory: Path, manifest: Mapping[str, Any]) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for filename, payload in output_payloads(manifest).items():
        destination = output_directory / filename
        rendered = _serialized(payload)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_directory, delete=False
        ) as handle:
            handle.write(rendered)
            temporary = Path(handle.name)
        os.replace(temporary, destination)


def _strip_build_metadata(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: _strip_build_metadata(value)
            for key, value in payload.items()
            if key != "generated_at"
        }
    if isinstance(payload, list):
        return [_strip_build_metadata(value) for value in payload]
    return payload


def check_outputs(output_directory: Path, manifest: Mapping[str, Any]) -> list[str]:
    differences: list[str] = []
    for filename, expected in output_payloads(manifest).items():
        destination = output_directory / filename
        if not destination.exists():
            differences.append(f"missing {destination}")
            continue
        try:
            actual = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            differences.append(f"cannot read {destination}: {exc}")
            continue
        if _strip_build_metadata(actual) != _strip_build_metadata(expected):
            differences.append(f"stale {destination}")
    return differences


def _print_diagnostics(project: AtlasProject, as_json: bool = False) -> None:
    if as_json:
        print(
            json.dumps(
                [item.as_dict() for item in project.diagnostics], ensure_ascii=False, indent=2
            )
        )
        return
    for item in project.diagnostics:
        location = item.source or "<project>"
        if item.pointer:
            location += item.pointer
        print(f"{location}: {item.severity}: [{item.code}] {item.message}")
    print(
        f"Atlas validation: {len(project.errors)} error(s), "
        f"{len(project.warnings)} warning(s), {len(project.documents)} document(s)."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("validate", "build"), help="validate content or build static manifests"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=repository_root(),
        help="repository root (default: auto-detected)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="manifest directory (default: <root>/platform/generated)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as build failures")
    parser.add_argument("--json", action="store_true", help="print validation diagnostics as JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files without rewriting them (build only)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    output_directory = (args.output_dir or root / "platform/generated").resolve()
    project = discover_documents(root)
    _print_diagnostics(project, as_json=args.json)
    failed = bool(project.errors) or (args.strict and bool(project.warnings))
    if args.command == "validate":
        return 1 if failed else 0
    if failed:
        print("Manifest was not generated because validation failed.", file=sys.stderr)
        return 1

    manifest = build_manifest(project)
    if args.check:
        differences = check_outputs(output_directory, manifest)
        for difference in differences:
            print(difference, file=sys.stderr)
        return 1 if differences else 0
    write_outputs(output_directory, manifest)
    print(
        f"Generated {len(output_payloads(manifest))} manifest files in "
        f"{_repo_relative(output_directory, root)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
