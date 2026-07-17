from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY_ROOT / "platform/scripts"
sys.path.insert(0, str(SCRIPTS))

import glossary  # noqa: E402


class GlossaryTestCase(unittest.TestCase):
    def test_repository_glossary_validates_and_renders_bilingual_terms(self) -> None:
        data = glossary.load_and_validate(REPOSITORY_ROOT)
        rendered = glossary.render(data)
        self.assertIn("최대우도추정", rendered)
        self.assertIn('lang="en">Maximum Likelihood Estimation', rendered)
        self.assertIn("#term-likelihood", rendered)

    def test_duplicate_identifiers_fail_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root, duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate glossary id"):
                glossary.load_and_validate(root)

    def test_build_check_detects_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root)
            glossary.build(root)
            glossary.build(root, check=True)
            (root / glossary.OUTPUT).write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale"):
                glossary.build(root, check=True)

    def test_flagship_inline_terms_match_the_central_glossary_exactly(self) -> None:
        """Keep chapter tooltips and the canonical glossary from drifting apart."""

        data = glossary.load_and_validate(REPOSITORY_ROOT)
        definitions = {
            term["en"].casefold(): term["short"] for term in data["terms"]
        }
        chapters = (
            "content/concepts/robotics/jacobian.qmd",
            "content/concepts/statistics/maximum-likelihood-estimation.qmd",
            "content/concepts/estimation/kalman-filter.qmd",
        )
        term_pattern = re.compile(r"\{\.atlas-term\b(?P<attributes>[^}]*)\}")
        attribute_pattern = re.compile(r'(?P<name>data-(?:en|definition))="(?P<value>[^"]*)"')

        for relative_path in chapters:
            source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
            terms_found = 0
            for match in term_pattern.finditer(source):
                attributes = {
                    item.group("name"): item.group("value")
                    for item in attribute_pattern.finditer(match.group("attributes"))
                }
                self.assertIn("data-en", attributes, relative_path)
                self.assertIn("data-definition", attributes, relative_path)
                english = attributes["data-en"]
                self.assertIn(
                    english.casefold(),
                    definitions,
                    f"{relative_path}: '{english}' is missing from the central glossary",
                )
                self.assertEqual(
                    attributes["data-definition"],
                    definitions[english.casefold()],
                    f"{relative_path}: '{english}' has drifted from the central glossary",
                )
                terms_found += 1
            self.assertGreater(terms_found, 0, f"No inline terms found in {relative_path}")

    def _write_fixture(self, root: Path, *, duplicate: bool = False) -> None:
        source = root / glossary.SOURCE
        schema = root / glossary.SCHEMA
        source.parent.mkdir(parents=True)
        schema.parent.mkdir(parents=True)
        schema.write_text(
            (REPOSITORY_ROOT / glossary.SCHEMA).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        terms = [
            {"id": "likelihood", "ko": "우도", "en": "likelihood", "short": "정의"},
            {
                "id": "likelihood" if duplicate else "mle",
                "ko": "최대우도추정",
                "en": "Maximum Likelihood Estimation",
                "abbr": "MLE",
                "short": "정의",
                "related": ["likelihood"],
            },
        ]
        source.write_text(
            yaml.safe_dump({"schema_version": "1.0.0", "terms": terms}, allow_unicode=True),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
