"""Regression tests for EPUB post-processing."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import package_epub_assets  # noqa: E402

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


def captioned_mermaid_xhtml(anchor: str) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="{XHTML_NAMESPACE}">
<head><title>captioned Mermaid</title></head>
<body>
<p><figure class></p>
<div><p><img src="../media/file9.png" alt="" /></p></div>
<p>{anchor}<figcaption> 칼만 <em>필터</em> 흐름 &amp; 보정 </figcaption> </figure></p>
<p><span id="p-keep" class="paragraph-anchor"></span>이어지는 본문</p>
</body>
</html>
""".encode()


def valid_captioned_mermaid_xhtml() -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="{XHTML_NAMESPACE}">
<head><title>captioned Mermaid</title></head>
<body>
<figure class="figure">
<div><p><img src="../media/file9.png" alt="칼만 필터 흐름" /></p></div>
<figcaption>칼만 필터 흐름</figcaption>
</figure>
</body>
</html>
""".encode()


@pytest.mark.parametrize(
    "anchor",
    (
        "",
        '<span id="p-5445d2fc" class="paragraph-anchor"></span>',
        "<span class='paragraph-anchor extra' id='p-other' />",
    ),
)
def test_repair_captioned_mermaid_with_optional_paragraph_anchor(anchor: str) -> None:
    repaired = package_epub_assets._repair_xhtml(
        captioned_mermaid_xhtml(anchor),
        "EPUB/text/ch022.xhtml",
    )

    root = ET.fromstring(repaired)
    figure = root.find(f".//{{{XHTML_NAMESPACE}}}figure")
    assert figure is not None
    assert figure.get("class") == "figure"

    image = figure.find(f".//{{{XHTML_NAMESPACE}}}img")
    caption = figure.find(f"{{{XHTML_NAMESPACE}}}figcaption")
    assert image is not None
    assert image.get("alt") == "칼만 필터 흐름 & 보정"
    assert caption is not None
    assert "".join(caption.itertext()).strip() == "칼만 필터 흐름 & 보정"

    document = repaired.decode()
    assert "p-5445d2fc" not in document
    assert "p-other" not in document
    assert 'id="p-keep"' in document
    assert "<p><figure" not in document
    assert "</figure></p>" not in document


def test_repair_leaves_valid_captioned_mermaid_unchanged() -> None:
    payload = valid_captioned_mermaid_xhtml()

    assert package_epub_assets._repair_xhtml(payload, "EPUB/text/ch022.xhtml") == payload


def test_repair_is_idempotent() -> None:
    payload = captioned_mermaid_xhtml(
        '<span id="p-5445d2fc" class="paragraph-anchor"></span>'
    )

    repaired = package_epub_assets._repair_xhtml(payload, "EPUB/text/ch022.xhtml")

    assert package_epub_assets._repair_xhtml(repaired, "EPUB/text/ch022.xhtml") == repaired


def test_repair_rejects_nonempty_paragraph_anchor_without_consuming_it() -> None:
    payload = captioned_mermaid_xhtml(
        '<span id="p-content" class="paragraph-anchor">보존할 내용</span>'
    )
    document = payload.decode()

    assert package_epub_assets._repair_mermaid_figures(document) == document
    with pytest.raises(ValueError, match="cannot package malformed EPUB XHTML"):
        package_epub_assets._repair_xhtml(payload, "EPUB/text/ch022.xhtml")
