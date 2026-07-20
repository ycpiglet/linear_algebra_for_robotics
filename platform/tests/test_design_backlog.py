from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY_ROOT / "platform/scripts"
sys.path.insert(0, str(SCRIPTS))

import design_backlog  # noqa: E402


class DesignBacklogTestCase(unittest.TestCase):
    def test_repository_backlog_is_valid(self) -> None:
        items, diagnostics = design_backlog.validate_backlog(REPOSITORY_ROOT)
        self.assertGreaterEqual(len(items), 10)
        self.assertEqual([], diagnostics, "\n".join(map(str, diagnostics)))

    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        schema_dir = root / "platform/schemas"
        schema_dir.mkdir(parents=True)
        source_schema = REPOSITORY_ROOT / design_backlog.SCHEMA_PATH
        (schema_dir / source_schema.name).write_text(
            json.dumps(json.loads(source_schema.read_text(encoding="utf-8")), indent=2),
            encoding="utf-8",
        )
        (root / design_backlog.ITEMS_DIR).mkdir(parents=True)
        return temporary, root

    def valid_item(self, identifier: str, **overrides: object) -> dict[str, object]:
        item: dict[str, object] = {
            "schema_version": 1,
            "id": identifier,
            "title": identifier,
            "area": "governance",
            "status": "planned",
            "priority": "P1",
            "change_class": "governance",
            "version_impact": "none",
            "owner_role": "publishing-ops-steward",
            "review_roles": [],
            "branch": None,
            "dependencies": [],
            "decision_refs": [],
            "decision_needed": [],
            "blocker": None,
            "scope": {"in": ["test"], "out": []},
            "change_paths": {
                "read": [],
                "write": ["test"],
                "exclusive_locks": [],
                "generated": [],
            },
            "verification": {
                "source_contract": ["test"],
                "rendered_contract": [],
                "post_merge": [],
            },
            "rollback": {
                "triggers": ["test failure"],
                "unit": "merge_commit",
                "steps": ["revert"],
                "compatibility_preserved": [],
            },
            "definition_of_done": ["validated"],
            "evidence": {
                "issue": None,
                "pr": None,
                "ci_runs": [],
                "rendered_artifacts": [],
                "last_known_good": None,
            },
            "last_reviewed": "2026-07-20",
        }
        item.update(overrides)
        return item

    def write_item(self, root: Path, item: dict[str, object]) -> None:
        identifier = str(item["id"])
        path = root / design_backlog.ITEMS_DIR / f"{identifier}.yml"
        path.write_text(yaml.safe_dump(item, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_dependency_cycle_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        self.write_item(root, self.valid_item("PUB-001", dependencies=["PUB-002"]))
        self.write_item(root, self.valid_item("PUB-002", dependencies=["PUB-001"]))

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("dependency.cycle", {item.code for item in diagnostics})

    def test_active_exclusive_lock_conflict_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        change_paths = {
            "read": [],
            "write": ["Makefile"],
            "exclusive_locks": ["ci-control-plane"],
            "generated": [],
        }
        self.write_item(
            root,
            self.valid_item(
                "PUB-001",
                status="in_progress",
                branch="one",
                change_paths=change_paths,
            ),
        )
        self.write_item(
            root,
            self.valid_item(
                "PUB-002",
                status="in_review",
                branch="two",
                change_paths=change_paths,
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("lock.conflict", {item.code for item in diagnostics})

    def test_ready_item_requires_done_dependencies(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        self.write_item(root, self.valid_item("PUB-001"))
        self.write_item(
            root,
            self.valid_item("PUB-002", status="ready", dependencies=["PUB-001"]),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("dependency.unfinished", {item.code for item in diagnostics})
