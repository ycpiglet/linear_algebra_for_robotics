from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY_ROOT / "platform/scripts"
sys.path.insert(0, str(SCRIPTS))

import atlas  # noqa: E402


class AtlasTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_qmd(self, relative: str, front_matter: str, body: str = "본문") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{front_matter.strip()}\n---\n\n{body}\n", encoding="utf-8")
        return path

    def codes(self, project: atlas.AtlasProject, severity: str | None = None) -> set[str]:
        return {
            item.code
            for item in project.diagnostics
            if severity is None or item.severity == severity
        }

    def write_valid_fixture(self) -> None:
        self.write_qmd(
            "content/concepts/math/error.qmd",
            """
id: math.error
title: 오차
aliases: [error]
domain: math
one_line: 목표값과 실제값의 차이
difficulty: 1
prerequisites:
  intuition:
    required: []
relations: {}
""",
        )
        self.write_qmd(
            "content/concepts/control/feedback.qmd",
            """
id: control.feedback
title: 피드백
domain: control
one_line: 결과를 입력에 되돌려 오차를 줄이는 구조
difficulty: 1
prerequisites:
  intuition:
    helpful:
      - concept: math.error
        competency: explain
        reason: 오차를 정의하기 위해
relations:
  used_in: [control.pid]
""",
        )
        self.write_qmd(
            "content/concepts/control/pid.qmd",
            """
id: control.pid
title: PID 제어
aliases: [PID controller]
domain: control
one_line: 현재·누적·변화 오차를 조합하는 피드백 제어기
difficulty: 2
importance: 5
importance_note: 여러 제어 장을 잇는 기준 구조
practice_frequency: 5
practice_frequency_note: 제어 구현과 로그에서 반복 사용
application_areas: [제어, 로봇공학]
reading_time: 18
prerequisites:
  intuition:
    required:
      - concept: control.feedback
        competency: explain
        reason: 폐루프 구조를 이해하기 위해
        diagnostic: open loop와 feedback의 차이는?
    not-required: [math.error]
  derivation:
    required: [math.error]
relations:
  derived-from: [control.feedback]
review:
  recall: P, I, D의 역할을 설명한다.
""",
        )
        self.write_qmd(
            "content/proofs/pid-stability.qmd",
            """
id: proof.pid_stability
title: 단순 PID 폐루프 안정성
statement: 특정 1차 plant에서 안정 조건을 보인다.
concepts: [control.pid]
dependencies: []
assumptions: [선형 시불변 plant]
level: finite
""",
        )
        self.write_qmd(
            "content/paths/pid.qmd",
            """
id: path.pid
title: PID 이해하기
summary: 직관에서 유도까지
stages:
  - id: intuition
    title: 직관
    steps:
      - concept: math.error
        depth: intuition
      - concept: control.feedback
        depth: intuition
      - concept: control.pid
        depth: intuition
  - id: derive
    title: 유도
    steps:
      - concept: control.pid
        depth: derivation
        optional: true
""",
        )

    def test_json_schemas_are_valid_draft_2020_12(self) -> None:
        for path in sorted((REPOSITORY_ROOT / "platform/schemas").glob("*.schema.json")):
            with self.subTest(schema=path.name):
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))

    def test_progress_schema_accepts_reader_ui_state(self) -> None:
        schema = json.loads(
            (REPOSITORY_ROOT / "platform/schemas/progress.schema.json").read_text(
                encoding="utf-8"
            )
        )
        payload = {
            "schema_version": "1.0.0",
            "exported_at": "2026-07-16T00:00:00Z",
            "items": {},
            "learning_stack": [],
            "ui_state": {
                "depth": {"estimation.kalman_filter": "derivation"},
                "favorites": {
                    "/kalman.html": {
                        "url": "/kalman.html",
                        "title": "칼만 필터",
                        "updatedAt": "2026-07-16T00:00:00Z",
                    }
                },
                "bookmarks": {
                    "/kalman.html#prediction": {
                        "url": "/kalman.html#prediction",
                        "pageTitle": "칼만 필터",
                        "sectionId": "prediction",
                        "sectionTitle": "예측",
                        "updatedAt": "2026-07-16T00:00:00Z",
                    }
                },
                "last_read": {
                    "/kalman.html": {
                        "url": "https://example.test/kalman.html",
                        "title": "칼만 필터",
                        "sectionId": "prediction",
                        "sectionTitle": "예측",
                        "ratio": 0.42,
                        "updatedAt": "2026-07-16T00:00:00Z",
                    }
                },
            },
        }

        errors = list(Draft202012Validator(schema).iter_errors(payload))
        self.assertFalse(errors, [error.message for error in errors])

    def test_build_normalizes_metadata_and_generates_backlinks(self) -> None:
        self.write_valid_fixture()
        project = atlas.discover_documents(self.root)

        self.assertFalse(project.errors, [item.as_dict() for item in project.errors])
        self.assertFalse(project.warnings, [item.as_dict() for item in project.warnings])

        manifest = atlas.build_manifest(project, generated_at="2026-01-01T00:00:00Z")
        by_id = {item["id"]: item for item in manifest["concepts"]}
        pid = by_id["control.pid"]
        feedback = by_id["control.feedback"]

        required = pid["prerequisites"]["intuition"]["required"][0]
        self.assertEqual("control.feedback", required["concept"])
        self.assertEqual("explain", required["competency"])
        self.assertEqual("/content/concepts/control/pid.html", pid["url"])
        self.assertEqual("content/concepts/control/pid.qmd", pid["source"])
        self.assertEqual(5, pid["importance"])
        self.assertEqual(5, pid["practice_frequency"])
        self.assertEqual(["제어", "로봇공학"], pid["application_areas"])

        required_by = feedback["backlinks"]["required_by"]
        self.assertEqual("control.pid", required_by[0]["concept"])
        self.assertEqual("intuition", required_by[0]["depth"])
        self.assertEqual("path.pid", pid["backlinks"]["paths"][0]["id"])
        self.assertEqual("proof.pid_stability", pid["backlinks"]["proofs"][0]["id"])

        graph_edges = manifest["graph"]["edges"]
        self.assertTrue(
            any(
                edge["type"] == "prerequisite"
                and edge["source"] == "control.feedback"
                and edge["target"] == "control.pid"
                for edge in graph_edges
            )
        )
        self.assertIn("pid controller", manifest["indexes"]["aliases"])

    def test_required_prerequisite_cycle_is_an_error(self) -> None:
        for source, target in (("math.a", "math.b"), ("math.b", "math.a")):
            self.write_qmd(
                f"content/concepts/{source[-1]}.qmd",
                f"""
id: {source}
title: {source}
domain: math
one_line: cycle fixture
prerequisites:
  intuition:
    required: [{target}]
""",
            )

        project = atlas.discover_documents(self.root)
        self.assertIn("prerequisite.cycle", self.codes(project, "error"))

    def test_helpful_edges_do_not_create_a_required_cycle(self) -> None:
        for source, target in (("math.a", "math.b"), ("math.b", "math.a")):
            self.write_qmd(
                f"content/concepts/{source[-1]}.qmd",
                f"""
id: {source}
title: {source}
domain: math
one_line: helpful fixture
prerequisites:
  intuition:
    helpful: [{target}]
""",
            )

        project = atlas.discover_documents(self.root)
        self.assertNotIn("prerequisite.cycle", self.codes(project, "error"))
        self.assertFalse(project.errors)

    def test_unresolved_required_prerequisite_is_an_error(self) -> None:
        self.write_qmd(
            "content/concepts/control/pid.qmd",
            """
id: control.pid
title: PID
domain: control
one_line: controller
prerequisites:
  intuition:
    required: [control.feedback]
""",
        )
        project = atlas.discover_documents(self.root)
        self.assertIn("prerequisite.unresolved", self.codes(project, "error"))

    def test_unresolved_relation_is_a_warning_and_is_preserved(self) -> None:
        self.write_qmd(
            "content/concepts/control/pid.qmd",
            """
id: control.pid
title: PID
domain: control
one_line: controller
relations:
  used_in: [robot.joint_control]
""",
        )
        project = atlas.discover_documents(self.root)
        self.assertFalse(project.errors)
        self.assertIn("relation.unresolved", self.codes(project, "warning"))

        manifest = atlas.build_manifest(project, generated_at="2026-01-01T00:00:00Z")
        unresolved = {node["id"]: node for node in manifest["graph"]["nodes"]}
        self.assertFalse(unresolved["robot.joint_control"]["resolved"])
        edge = next(edge for edge in manifest["graph"]["edges"] if edge["type"] == "relation")
        self.assertFalse(edge["resolved"])

    def test_proof_dependency_cycle_is_an_error(self) -> None:
        self.write_qmd(
            "content/concepts/probability/lln.qmd",
            """
id: probability.lln
title: 대수의 법칙
domain: probability
one_line: 표본평균의 수렴
""",
        )
        for source, target in (("proof.a", "proof.b"), ("proof.b", "proof.a")):
            self.write_qmd(
                f"content/proofs/{source[-1]}.qmd",
                f"""
id: {source}
title: {source}
dependencies: [{target}]
concepts: [probability.lln]
""",
            )
        project = atlas.discover_documents(self.root)
        self.assertIn("proof.cycle", self.codes(project, "error"))

    def test_proof_authoring_aliases_generate_concept_backlinks(self) -> None:
        for identifier in ("probability.base", "probability.result"):
            self.write_qmd(
                f"content/concepts/{identifier.rsplit('.', 1)[-1]}.qmd",
                f"""
id: {identifier}
title: {identifier}
domain: probability
one_line: proof fixture
""",
            )
        self.write_qmd(
            "content/proofs/result.qmd",
            """
id: proof.result
title: Result proof
domain: probability
one-line: proves a result
proves: [probability.result]
prerequisites:
  proof:
    required:
      - concept: probability.base
        competency: proof
""",
        )

        project = atlas.discover_documents(self.root)
        self.assertFalse(project.errors, [item.as_dict() for item in project.errors])
        manifest = atlas.build_manifest(project, generated_at="2026-01-01T00:00:00Z")
        concepts = {item["id"]: item for item in manifest["concepts"]}
        proof = manifest["proofs"][0]
        self.assertEqual(["probability.result"], proof["concepts"])
        self.assertEqual("prove", proof["prerequisites"]["proof"]["required"][0]["competency"])
        self.assertEqual(
            "proof.result", concepts["probability.result"]["backlinks"]["proofs"][0]["id"]
        )
        self.assertEqual(
            "proof.result",
            concepts["probability.base"]["backlinks"]["required_by_proofs"][0]["id"],
        )

    def test_path_depth_times_and_legacy_entry_aliases_are_compiled(self) -> None:
        for identifier in ("probability.markov_chain", "probability.mcmc"):
            self.write_qmd(
                f"content/concepts/{identifier.rsplit('.', 1)[-1]}.qmd",
                f"""
id: {identifier}
title: {identifier}
domain: probability
one_line: path fixture
""",
            )
        self.write_qmd(
            "content/paths/mcmc.qmd",
            """
id: path.mcmc
title: MCMC path
one-line: shortest path
estimated_time:
  intuition: 20분
  proof: 4시간
entry-concepts: [probability.markov_chain]
exit-concept: probability.mcmc
""",
        )

        project = atlas.discover_documents(self.root)
        self.assertFalse(project.errors, [item.as_dict() for item in project.errors])
        path = atlas.build_manifest(project, generated_at="2026-01-01T00:00:00Z")["paths"][0]
        self.assertEqual(
            {"intuition": "20분", "proof": "4시간"},
            path["estimated_time"],
        )
        self.assertEqual(
            ["probability.markov_chain", "probability.mcmc"],
            [step["concept"] for step in path["steps"]],
        )

    def test_schema_rejects_unstable_id_and_unknown_depth(self) -> None:
        self.write_qmd(
            "content/concepts/bad.qmd",
            """
id: Bad ID
title: Bad
domain: math
one_line: invalid
prerequisites:
  beginner:
    required: []
""",
        )
        project = atlas.discover_documents(self.root)
        self.assertIn("schema.concept", self.codes(project, "error"))

    def test_build_outputs_and_check_are_semantically_reproducible(self) -> None:
        self.write_valid_fixture()
        project = atlas.discover_documents(self.root)
        manifest = atlas.build_manifest(project, generated_at="2026-01-01T00:00:00Z")
        output = self.root / "platform/generated"
        atlas.write_outputs(output, manifest)

        later_manifest = atlas.build_manifest(project, generated_at="2027-01-01T00:00:00Z")
        self.assertEqual([], atlas.check_outputs(output, later_manifest))
        self.assertEqual(
            {"backlinks.json", "concept-manifest.json", "knowledge-graph.json", "paths.json"},
            {path.name for path in output.iterdir()},
        )


if __name__ == "__main__":
    unittest.main()
