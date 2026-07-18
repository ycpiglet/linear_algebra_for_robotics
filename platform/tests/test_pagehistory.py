from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY_ROOT / "platform/scripts"
sys.path.insert(0, str(SCRIPTS))

import pagehistory  # noqa: E402


class PageHistoryTestCase(unittest.TestCase):
    def test_build_covers_root_and_content_pages_with_full_entries(self) -> None:
        output = pagehistory.build(REPOSITORY_ROOT)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("index.qmd", data)
        self.assertIn("content/concepts/estimation/kalman-filter.qmd", data)
        self.assertNotIn("platform/templates/concept.qmd", data,
                         "platform/**는 렌더 대상이 아니므로 이력에서도 제외")
        entry = data["index.qmd"][0]
        for key in ("sha", "date", "author", "subject"):
            self.assertIn(key, entry)
        self.assertRegex(entry["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertLessEqual(len(data["index.qmd"]), pagehistory.LIMIT)


if __name__ == "__main__":
    unittest.main()
