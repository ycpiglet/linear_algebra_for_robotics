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

EXPECTED_INITIAL_IDS = {f"PUB-{number:03d}" for number in range(1, 16)}


class DesignBacklogTestCase(unittest.TestCase):
    def test_repository_backlog_is_valid(self) -> None:
        items, diagnostics = design_backlog.validate_backlog(REPOSITORY_ROOT)
        self.assertTrue(EXPECTED_INITIAL_IDS.issubset(items))
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
            "status_reason": None,
            "superseded_by": None,
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
                "post_merge": [],
                "last_known_good": None,
                "revert_ref": None,
                "follow_up": None,
            },
            "last_reviewed": "2026-07-20",
        }
        item.update(overrides)
        return item

    def write_item(self, root: Path, item: dict[str, object]) -> None:
        identifier = str(item["id"])
        path = root / design_backlog.ITEMS_DIR / f"{identifier}.yml"
        path.write_text(yaml.safe_dump(item, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def write_raw_item(self, root: Path, identifier: str, source: str) -> None:
        path = root / design_backlog.ITEMS_DIR / f"{identifier}.yml"
        path.write_text(source, encoding="utf-8")

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

    def test_schema_invalid_nested_values_are_diagnostics_not_exceptions(self) -> None:
        malformed_values = {
            "verification": [],
            "dependencies": None,
            "change_paths": [],
        }
        for field, value in malformed_values.items():
            with self.subTest(field=field):
                temporary, root = self.make_project()
                self.addCleanup(temporary.cleanup)
                self.write_item(
                    root,
                    self.valid_item("PUB-001", status="ready", **{field: value}),
                )

                _, diagnostics = design_backlog.validate_backlog(root)

                self.assertIn("schema.invalid", {item.code for item in diagnostics})

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        self.write_raw_item(
            root,
            "PUB-001",
            "schema_version: 1\nid: PUB-001\nstatus: planned\nstatus: cancelled\n",
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("yaml.invalid", {item.code for item in diagnostics})
        self.assertIn("duplicate key", "\n".join(map(str, diagnostics)))

    def test_invalid_utf8_work_item_is_reported(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        path = root / design_backlog.ITEMS_DIR / "PUB-001.yml"
        path.write_bytes(b"\xff")

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("yaml.invalid", {item.code for item in diagnostics})

    def test_invalid_utf8_schema_is_reported(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / design_backlog.SCHEMA_PATH).write_bytes(b"\xff")

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("schema.unavailable", {item.code for item in diagnostics})

    def test_truncated_or_boolean_schema_is_rejected(self) -> None:
        for schema in ({}, True):
            with self.subTest(schema=schema):
                temporary, root = self.make_project()
                self.addCleanup(temporary.cleanup)
                (root / design_backlog.SCHEMA_PATH).write_text(
                    json.dumps(schema), encoding="utf-8"
                )

                _, diagnostics = design_backlog.validate_backlog(root)

                self.assertIn("schema.unavailable", {item.code for item in diagnostics})

    def test_unresolvable_schema_reference_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        schema_path = root / design_backlog.SCHEMA_PATH
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["properties"]["scope"] = {"$ref": "#/$defs/missing"}
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("schema.unavailable", {item.code for item in diagnostics})

    def test_coordinated_schema_and_item_shape_drift_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        schema_path = root / design_backlog.SCHEMA_PATH
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["properties"]["change_paths"] = {"type": "array"}
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        self.write_item(root, self.valid_item("PUB-001", change_paths=[]))

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("schema.contract_drift", {item.code for item in diagnostics})

    def test_malformed_schema_required_type_is_reported(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        schema_path = root / design_backlog.SCHEMA_PATH
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["required"] = 1
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("schema.unavailable", {item.code for item in diagnostics})

    def test_blocked_item_keeps_exclusive_lock(self) -> None:
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
                status="blocked",
                branch="blocked-branch",
                blocker="waiting for external state",
                change_paths=change_paths,
            ),
        )
        self.write_item(
            root,
            self.valid_item(
                "PUB-002",
                status="in_progress",
                branch="active-branch",
                change_paths=change_paths,
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("lock.conflict", {item.code for item in diagnostics})

    def test_active_items_cannot_share_branch_or_write_path(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        change_paths = {
            "read": [],
            "write": ["Makefile"],
            "exclusive_locks": [],
            "generated": [],
        }
        for identifier in ("PUB-001", "PUB-002"):
            self.write_item(
                root,
                self.valid_item(
                    identifier,
                    status="in_progress",
                    branch="shared-branch",
                    change_paths=change_paths,
                ),
            )

        _, diagnostics = design_backlog.validate_backlog(root)
        codes = {item.code for item in diagnostics}

        self.assertIn("branch.conflict", codes)
        self.assertIn("path.conflict", codes)

    def test_glob_and_concrete_write_path_overlap_is_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        for identifier, branch, write_path in (
            ("PUB-001", "glob-branch", "platform/design/**"),
            ("PUB-002", "file-branch", "platform/design/README.md"),
        ):
            change_paths = {
                "read": [],
                "write": [write_path],
                "exclusive_locks": [],
                "generated": [],
            }
            self.write_item(
                root,
                self.valid_item(
                    identifier,
                    status="in_progress",
                    branch=branch,
                    change_paths=change_paths,
                ),
            )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("path.conflict", {item.code for item in diagnostics})

    def test_recursive_glob_matches_direct_child_write_path(self) -> None:
        self.assertTrue(
            design_backlog._path_specs_overlap("content/**/*.qmd", "content/example.qmd")
        )

    def test_parent_and_child_write_paths_overlap(self) -> None:
        self.assertTrue(
            design_backlog._path_specs_overlap("assets/styles", "assets/styles/theme.scss")
        )
        self.assertTrue(design_backlog._path_specs_overlap("foo", "foo/**"))

    def test_malformed_character_class_path_is_rejected_without_exception(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        change_paths = {
            "read": [],
            "write": ["assets/[z-a].scss"],
            "exclusive_locks": [],
            "generated": [],
        }
        self.write_item(
            root,
            self.valid_item(
                "PUB-001",
                status="in_progress",
                branch="valid-branch",
                change_paths=change_paths,
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("path.invalid", {item.code for item in diagnostics})

    def test_active_branch_must_be_valid_short_ref(self) -> None:
        for branch in (
            "not a valid branch",
            "refs/heads/feature/x",
            "bad..branch",
            "HEAD",
            "main",
        ):
            with self.subTest(branch=branch):
                temporary, root = self.make_project()
                self.addCleanup(temporary.cleanup)
                self.write_item(
                    root,
                    self.valid_item(
                        "PUB-001",
                        status="in_progress",
                        branch=branch,
                    ),
                )

                _, diagnostics = design_backlog.validate_backlog(root)

                self.assertIn("branch.invalid", {item.code for item in diagnostics})

    def test_empty_source_contract_is_diagnostic_not_exception(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        verification = {
            "source_contract": [],
            "rendered_contract": [],
            "post_merge": [],
        }
        self.write_item(
            root,
            self.valid_item("PUB-001", status="ready", verification=verification),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("verification.missing", {item.code for item in diagnostics})

    def test_whitespace_only_contract_and_evidence_are_rejected(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        verification = {
            "source_contract": [" "],
            "rendered_contract": [],
            "post_merge": [],
        }
        evidence = {
            "issue": None,
            "pr": 1,
            "ci_runs": [" "],
            "rendered_artifacts": [],
            "post_merge": [],
            "last_known_good": " ",
            "revert_ref": None,
            "follow_up": None,
        }
        self.write_item(
            root,
            self.valid_item(
                "PUB-001",
                status="in_review",
                branch="review-branch",
                verification=verification,
                evidence=evidence,
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("text.invalid", {item.code for item in diagnostics})

    def test_in_review_requires_pr_ci_and_last_known_good(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        self.write_item(
            root,
            self.valid_item("PUB-001", status="in_review", branch="review-branch"),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("evidence.missing", {item.code for item in diagnostics})

    def test_done_requires_rendered_and_post_merge_evidence(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        verification = {
            "source_contract": ["make test"],
            "rendered_contract": ["web smoke"],
            "post_merge": ["main smoke"],
        }
        evidence = {
            "issue": None,
            "pr": 1,
            "ci_runs": ["https://example.test/run/1"],
            "rendered_artifacts": [],
            "post_merge": [],
            "last_known_good": "abc123",
            "revert_ref": None,
            "follow_up": None,
        }
        self.write_item(
            root,
            self.valid_item(
                "PUB-001", status="done", verification=verification, evidence=evidence
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)
        codes = {item.code for item in diagnostics}

        self.assertIn("evidence.rendered_missing", codes)
        self.assertIn("evidence.post_merge_missing", codes)

    def test_rolled_back_requires_revert_and_follow_up(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        evidence = {
            "issue": None,
            "pr": 1,
            "ci_runs": ["https://example.test/run/1"],
            "rendered_artifacts": [],
            "post_merge": ["https://example.test/run/2"],
            "last_known_good": "abc123",
            "revert_ref": None,
            "follow_up": None,
        }
        self.write_item(
            root,
            self.valid_item("PUB-001", status="rolled_back", evidence=evidence),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("rollback.evidence_missing", {item.code for item in diagnostics})

    def test_ready_paths_must_be_concrete_repository_specs(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        change_paths = {
            "read": [],
            "write": ["대표 개념 장 1개"],
            "exclusive_locks": [],
            "generated": [],
        }
        self.write_item(
            root,
            self.valid_item("PUB-001", status="ready", change_paths=change_paths),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("path.invalid", {item.code for item in diagnostics})

    def test_ready_item_requires_write_path(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        change_paths = {
            "read": [],
            "write": [],
            "exclusive_locks": [],
            "generated": [],
        }
        self.write_item(
            root,
            self.valid_item("PUB-001", status="ready", change_paths=change_paths),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("path.write_missing", {item.code for item in diagnostics})

    def test_decision_reference_file_and_anchor_must_exist(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / "manual.md").write_text("# Existing heading\n", encoding="utf-8")
        self.write_item(
            root,
            self.valid_item(
                "PUB-001",
                decision_refs=["missing.md#heading", "manual.md#missing-heading"],
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)
        codes = {item.code for item in diagnostics}

        self.assertIn("decision_ref.missing", codes)
        self.assertIn("decision_ref.anchor_missing", codes)

    def test_invalid_utf8_decision_reference_is_reported(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / "manual.md").write_bytes(b"\xff")
        self.write_item(
            root,
            self.valid_item("PUB-001", decision_refs=["manual.md#heading"]),
        )

        _, diagnostics = design_backlog.validate_backlog(root)

        self.assertIn("decision_ref.unreadable", {item.code for item in diagnostics})

    def test_decision_reference_ignores_code_fences_and_supports_heading_forms(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / "manual.md").write_text(
            "```markdown\n# Fake heading\n{#fake-id}\n```\n\n"
            "# Real heading #\n\nSetext heading\n--------------\n",
            encoding="utf-8",
        )
        self.write_item(
            root,
            self.valid_item(
                "PUB-001",
                decision_refs=[
                    "manual.md#fake-heading",
                    "manual.md#fake-id",
                    "manual.md#real-heading",
                    "manual.md#setext-heading",
                    "manual.md#",
                ],
            ),
        )

        _, diagnostics = design_backlog.validate_backlog(root)
        messages = [
            item.message
            for item in diagnostics
            if item.code == "decision_ref.anchor_missing"
        ]

        self.assertEqual(3, len(messages))
        self.assertFalse(any("real-heading" in message for message in messages))
        self.assertFalse(any("setext-heading" in message for message in messages))

    def test_markdown_anchor_parser_ignores_metadata_comments_and_explicit_slug(self) -> None:
        text = (
            "---\ntitle: Fake\n---\n"
            "<!--\n# Comment heading\n-->\n"
            "## Visible heading {#custom-anchor}\n"
        )

        anchors = design_backlog._markdown_anchors(text)

        self.assertEqual({"custom-anchor"}, anchors)

    def test_comment_marker_inside_fence_does_not_hide_later_heading(self) -> None:
        text = "```html\n<!-- template comment\n```\n# Real heading\n"

        anchors = design_backlog._markdown_anchors(text)

        self.assertEqual({"real-heading"}, anchors)

    def test_fence_with_trailing_text_does_not_close_code_block(self) -> None:
        text = (
            "```text\ncode\n``` not-a-closing-fence\n# Still code\n```\n# Real heading\n"
        )

        anchors = design_backlog._markdown_anchors(text)

        self.assertEqual({"real-heading"}, anchors)

    def test_lone_surrogate_is_safe_diagnostic(self) -> None:
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        self.write_item(
            root,
            self.valid_item("PUB-001", decision_refs=["\ud800"]),
        )

        _, diagnostics = design_backlog.validate_backlog(root)
        rendered = "\n".join(map(str, diagnostics))

        self.assertIn("text.invalid", {item.code for item in diagnostics})
        rendered.encode("utf-8")
