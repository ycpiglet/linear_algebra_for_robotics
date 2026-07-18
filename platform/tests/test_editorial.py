from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY_ROOT / "platform/scripts"
sys.path.insert(0, str(SCRIPTS))

import editorial  # noqa: E402

CHAPTER = """# 칼만 필터

첫 문단이다. 자코비안은 선형화의 도구다.

필터는 상태를 업데이트한다. 그리고 **공분산**도 함께 갱신한다.

반복되는 문구다. 같은 내용.

반복되는 문구다. 같은 내용. 뒤에 덧붙은 구별 문장.
"""


def issue_body(page: str, quote: str, prefix: str = "", suffix: str = "",
               suggestion: str | None = None, comment: str = "표기 통일") -> str:
    """review-scripts.html의 issueUrl()이 만드는 본문과 같은 형식."""
    sections = [f"## 사유·코멘트\n\n{comment}"]
    if suggestion is not None:
        sections.append(f"## 수정안\n\n~~~\n{suggestion}\n~~~")
    sections.append(f"## 원문\n\n> {quote}")
    sections.append(f"## 위치\n\n- 페이지: {page}\n- 문단: `p-deadbeef`")
    payload = json.dumps({"v": 1, "page": page, "paragraph": "p-deadbeef",
                          "quote": quote, "prefix": prefix, "suffix": suffix},
                         ensure_ascii=False)
    sections.append(f"<!-- editorial-anchor {payload} -->")
    return "\n\n".join(sections)


def make_issue(number: int, body: str) -> dict:
    return {"number": number, "title": f"[교정] 테스트 (#{number})",
            "user": {"login": "editor-kim"}, "body": body}


class EditorialTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.source = self.root / "content/concepts/estimation/kalman-filter.qmd"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(CHAPTER, encoding="utf-8")
        # 이벤트 검증이 리포지토리의 실제 스키마를 쓰도록 복사한다.
        schema_target = self.root / editorial.SCHEMA
        schema_target.parent.mkdir(parents=True)
        schema_target.write_text(
            (REPOSITORY_ROOT / editorial.SCHEMA).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.page = ("https://ycpiglet.github.io/linear_algebra_for_robotics/review/"
                     "content/concepts/estimation/kalman-filter.html")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def apply(self, issues: list[dict]) -> list[editorial.Outcome]:
        return editorial.apply_issues(issues, self.root, git=False, today="2026-07-18")

    def test_issue_body_round_trip_parses(self) -> None:
        body = issue_body(self.page, "업데이트한다", suggestion="갱신한다")
        proposal = editorial.parse_issue(make_issue(7, body))
        assert proposal is not None
        self.assertEqual(proposal.quote, "업데이트한다")
        self.assertEqual(proposal.suggestion, "갱신한다")
        self.assertEqual(proposal.comment, "표기 통일")
        self.assertEqual(proposal.paragraph_id, "p-deadbeef")

    def test_page_url_maps_through_site_and_review_prefixes(self) -> None:
        for prefix in ("", "review/", "preview/pr-12/", "linear_algebra_for_robotics/review/"):
            url = f"https://example.org/{prefix}content/concepts/estimation/kalman-filter.html"
            self.assertEqual(editorial.page_to_source(url, self.root), self.source,
                             msg=f"prefix={prefix!r}")
        self.assertIsNone(editorial.page_to_source("https://example.org/none.html", self.root))

    def test_apply_replaces_plain_span_and_records_event(self) -> None:
        body = issue_body(self.page, "필터는 상태를 업데이트한다.",
                          suggestion="필터는 측정 갱신으로 상태를 고쳐 쓴다.")
        outcomes = self.apply([make_issue(12, body)])
        self.assertEqual(outcomes[0].action, "applied")
        text = self.source.read_text(encoding="utf-8")
        self.assertIn("측정 갱신으로 상태를 고쳐 쓴다", text)
        self.assertNotIn("업데이트한다", text)

        events_file = self.root / editorial.EVENTS_DIR / "2026-07.jsonl"
        record = json.loads(events_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["status"], "applied")
        self.assertEqual(record["actor_role"], "agent")
        self.assertEqual(record["links"]["source"], "issue:#12")
        self.assertEqual(record["instruction"], "표기 통일")
        editorial.validate_event(record, self.root)

    def test_markup_crossing_span_is_left_for_review(self) -> None:
        body = issue_body(self.page, "그리고 공분산도 함께",
                          suggestion="또한 공분산도 같이")
        outcomes = self.apply([make_issue(13, body)])
        self.assertEqual(outcomes[0].action, "needs-review")
        self.assertIn("공분산", self.source.read_text(encoding="utf-8"))

    def test_duplicate_quote_disambiguated_by_suffix(self) -> None:
        body = issue_body(self.page, "반복되는 문구다.", suffix="같은 내용. 뒤에 덧붙은",
                          suggestion="반복이 아닌 문구다.")
        outcomes = self.apply([make_issue(14, body)])
        self.assertEqual(outcomes[0].action, "applied")
        text = self.source.read_text(encoding="utf-8")
        self.assertEqual(text.count("반복되는 문구다."), 1)
        self.assertIn("반복이 아닌 문구다. 같은 내용. 뒤에 덧붙은", text)

    def test_duplicate_quote_without_context_is_ambiguous(self) -> None:
        body = issue_body(self.page, "반복되는 문구다.", suggestion="바꾼다")
        outcomes = self.apply([make_issue(15, body)])
        self.assertEqual(outcomes[0].action, "ambiguous")

    def test_comment_only_reports_source_location(self) -> None:
        body = issue_body(self.page, "자코비안은 선형화의 도구다.")
        outcomes = self.apply([make_issue(16, body)])
        self.assertEqual(outcomes[0].action, "comment-only")
        self.assertEqual(outcomes[0].file, "content/concepts/estimation/kalman-filter.qmd")
        self.assertEqual(outcomes[0].line, 3)

    def test_stale_quote_reports_not_found(self) -> None:
        body = issue_body(self.page, "이미 사라진 문장이다.", suggestion="무엇으로든")
        outcomes = self.apply([make_issue(17, body)])
        self.assertEqual(outcomes[0].action, "not-found")

    def test_invalid_event_rejected_by_schema(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema validation failed"):
            editorial.append_event({"id": "x", "date": "2026-07-18"}, self.root)


if __name__ == "__main__":
    unittest.main()
