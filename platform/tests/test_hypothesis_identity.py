from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
IDENTITY_FILTER = ROOT / "platform/extension/document-identity.lua"
CONTAINER = "robotics-math-atlas"
IDENTIFIER = "urn:robotics-math-atlas:document:v1:index.qmd"


def hypothesis_fingerprint(container: str, identifier: str) -> str:
    """Mirror the Hypothesis HTML metadata integration's urn:x-dc mapping."""
    return f"urn:x-dc:{quote(container, safe='')}/{quote(identifier, safe='')}"


def test_identity_filter_emits_both_dublin_core_components() -> None:
    source = IDENTITY_FILTER.read_text(encoding="utf-8")

    assert 'name="DC.relation.ispartof" content="robotics-math-atlas"' in source
    assert 'name="DC.identifier"' in source
    assert "urn:robotics-math-atlas:document:v1:" in source
    for forbidden in ("github.io", "linear_algebra_for_robotics", "/review/", "/preview/"):
        assert forbidden not in source


def test_old_and_new_pages_urls_share_one_hypothesis_fingerprint() -> None:
    old_url = "https://ycpiglet.github.io/linear_algebra_for_robotics/"
    new_url = "https://ycpiglet.github.io/robotics-math-atlas/"

    fingerprints = {
        url: hypothesis_fingerprint(CONTAINER, IDENTIFIER)
        for url in (old_url, new_url)
    }

    assert len(set(fingerprints.values())) == 1
    assert fingerprints[old_url] == (
        "urn:x-dc:robotics-math-atlas/"
        "urn%3Arobotics-math-atlas%3Adocument%3Av1%3Aindex.qmd"
    )
