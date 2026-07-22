from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

from pypdf.generic import ArrayObject, DictionaryObject, NameObject, StreamObject

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_outputs", ROOT / "scripts" / "verify_outputs.py"
)
assert SPEC and SPEC.loader
verify_outputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_outputs)


def _html(relative: str, body: str) -> str:
    identifier = (
        verify_outputs.DOCUMENT_ID_PREFIX
        + relative.removesuffix(".html").replace("/", "%2F")
        + ".qmd"
    )
    return f'<html><head><meta name="DC.identifier" content="{identifier}"></head>{body}</html>'


def _embedded_font(style: str) -> DictionaryObject:
    descriptor = DictionaryObject(
        {
            NameObject("/FontName"): NameObject(f"/ABCDEF+AtlasSansKR-{style}"),
            NameObject("/FontFile3"): StreamObject(),
        }
    )
    descendant = DictionaryObject(
        {
            NameObject("/BaseFont"): NameObject(f"/ABCDEF+AtlasSansKR-{style}"),
            NameObject("/FontDescriptor"): descriptor,
        }
    )
    return DictionaryObject(
        {
            NameObject("/BaseFont"): NameObject(f"/ABCDEF+AtlasSansKR-{style}"),
            NameObject("/DescendantFonts"): ArrayObject([descendant]),
        }
    )


def test_pdf_font_helpers_recognize_embedded_atlas_descendant_styles() -> None:
    regular = _embedded_font("Regular")
    bold = _embedded_font("Bold")

    assert verify_outputs._font_is_embedded(regular)
    assert verify_outputs._font_names(regular) == {"/ABCDEF+AtlasSansKR-Regular"}
    assert verify_outputs._embedded_atlas_styles(regular) == {"regular"}
    assert verify_outputs._embedded_atlas_styles(bold) == {"bold"}


def test_pdf_font_helper_rejects_unembedded_or_unrecognized_atlas_fonts() -> None:
    unembedded = _embedded_font("Regular")
    descriptor = unembedded["/DescendantFonts"][0]["/FontDescriptor"]
    del descriptor["/FontFile3"]
    unrelated = _embedded_font("Italic")

    assert verify_outputs._embedded_atlas_styles(unembedded) == set()
    assert verify_outputs._embedded_atlas_styles(unrelated) == set()


def _write_minimal_atlas_site(root: Path) -> None:
    atlas = root / "atlas.html"
    atlas.write_text(_html("atlas.html", "<main>atlas</main>"), encoding="utf-8")
    for relative in verify_outputs.FLAGSHIP_HTML:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _html(relative, '<main class="page-glossary--static"></main>'),
            encoding="utf-8",
        )
    for relative, payload in (
        ("assets/js/atlas.js", b"// fixture"),
        ("assets/fonts/AtlasSansKR-Regular.woff2", b"fixture"),
        ("assets/fonts/AtlasSansKR-Bold.woff2", b"fixture"),
        ("assets/fonts/OFL.txt", b"fixture"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _write_minimal_epub(
    path: Path,
    *,
    chapter_href: str = "ch2.xhtml#target",
    chapter_markup: str = '<math><mi>x</mi></math>',
    chapter_properties: str = "mathml",
) -> None:
    flagship_and_reference_titles = " ".join(
        (*verify_outputs.FLAGSHIP_TITLES, *verify_outputs.REFERENCE_TITLES)
    )
    package = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">atlas-test</dc:identifier>
    <dc:title>Atlas test</dc:title>
    <dc:language>ko</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml"
      properties="{chapter_properties}"/>
    <item id="ch2" href="text/ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="styles/epub.css" media-type="text/css"/>
    <item id="regular" href="fonts/AtlasSansKR-Regular.woff2" media-type="font/woff2"/>
    <item id="bold" href="fonts/AtlasSansKR-Bold.woff2" media-type="font/woff2"/>
    <item id="license" href="fonts/OFL.txt" media-type="text/plain"/>
  </manifest>
  <spine><itemref idref="ch1"/><itemref idref="ch2"/></spine>
</package>
"""
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    navigation = """<html xmlns="http://www.w3.org/1999/xhtml"
  xmlns:epub="http://www.idpf.org/2007/ops"><body>
  <nav epub:type="toc"><ol><li><a href="text/ch1.xhtml">장</a></li></ol></nav>
</body></html>"""
    chapter = (
        '<html><body><main class="page-glossary--static">'
        f"{flagship_and_reference_titles}"
        f"{chapter_markup}"
        f'<a href="{chapter_href}">next</a>'
        "</main></body></html>"
    )
    css = '@font-face{font-family:"Atlas Sans KR";src:url("../fonts/AtlasSansKR-Regular.woff2")} '
    font_fixture = b"0" * 100_001

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            b"application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("EPUB/package.opf", package)
        archive.writestr("EPUB/nav.xhtml", navigation)
        archive.writestr("EPUB/text/ch1.xhtml", chapter)
        archive.writestr("EPUB/text/ch2.xhtml", '<html><body id="target"></body></html>')
        archive.writestr("EPUB/styles/epub.css", css)
        archive.writestr("EPUB/fonts/AtlasSansKR-Regular.woff2", font_fixture)
        archive.writestr("EPUB/fonts/AtlasSansKR-Bold.woff2", font_fixture)
        archive.writestr("EPUB/fonts/OFL.txt", "SIL Open Font License fixture")


def test_html_verifier_accepts_valid_relative_link_and_fragment(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        '<a href="nested/page.html#answer">answer</a>', encoding="utf-8"
    )
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "page.html").write_text('<h2 id="answer">42</h2>', encoding="utf-8")

    assert verify_outputs.verify_html_tree(tmp_path) == []


def test_html_verifier_rejects_missing_and_source_links(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        '<a href="missing.html">missing</a><a href="chapter.qmd">source</a>', encoding="utf-8"
    )

    errors = verify_outputs.verify_html_tree(tmp_path)
    assert any("missing target" in error for error in errors)
    assert any("source-document link" in error for error in errors)


def test_html_verifier_checks_runtime_manifest_urls(tmp_path: Path) -> None:
    _write_minimal_atlas_site(tmp_path)
    generated = tmp_path / "platform" / "generated"
    generated.mkdir(parents=True)
    (generated / "concept-manifest.json").write_text(
        json.dumps(
            {
                "concepts": [
                    {"url": "/content/concepts/present.html#answer"},
                    {"url": "/content/concepts/missing.html"},
                ]
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "content" / "concepts"
    target.mkdir(parents=True, exist_ok=True)
    (target / "present.html").write_text(
        _html("content/concepts/present.html", '<h2 id="answer">42</h2>'),
        encoding="utf-8",
    )

    errors = verify_outputs.verify_html_tree(tmp_path)
    assert errors == [
        "platform/generated/concept-manifest.json: missing target for "
        "/content/concepts/missing.html"
    ]


def test_html_verifier_rejects_missing_duplicate_and_url_dependent_identity(
    tmp_path: Path,
) -> None:
    _write_minimal_atlas_site(tmp_path)
    flagship = tmp_path / verify_outputs.FLAGSHIP_HTML[0]
    flagship.write_text('<main class="page-glossary--static"></main>', encoding="utf-8")
    duplicate = tmp_path / verify_outputs.FLAGSHIP_HTML[1]
    duplicate.write_text(
        _html("atlas.html", '<main class="page-glossary--static"></main>'),
        encoding="utf-8",
    )
    dependent = tmp_path / verify_outputs.FLAGSHIP_HTML[2]
    dependent.write_text(
        '<meta name="DC.identifier" content="urn:robotics-math-atlas:document:v1:'
        'https%3A%2F%2Fycpiglet.github.io%2Flinear_algebra_for_robotics%2Fpage">'
        '<main class="page-glossary--static"></main>',
        encoding="utf-8",
    )

    errors = verify_outputs.verify_html_tree(tmp_path)
    assert any("expected exactly one DC.identifier, found 0" in error for error in errors)
    assert any("duplicate DC.identifier" in error for error in errors)
    assert any("URL-dependent DC.identifier" in error for error in errors)


def test_epub_verifier_checks_members_and_fragments(tmp_path: Path) -> None:
    epub = tmp_path / "valid.epub"
    _write_minimal_epub(epub)

    assert verify_outputs.verify_epub(epub) == []


def test_epub_verifier_rejects_qmd_link(tmp_path: Path) -> None:
    epub = tmp_path / "invalid.epub"
    _write_minimal_epub(epub, chapter_href="chapter.qmd")

    errors = verify_outputs.verify_epub(epub)
    assert any("source-document link" in error for error in errors)


def test_epub_verifier_rejects_non_xml_xhtml(tmp_path: Path) -> None:
    epub = tmp_path / "invalid-xhtml.epub"
    _write_minimal_epub(
        epub,
        chapter_markup='<math><mi>x</mi></math><input disabled>',
    )

    errors = verify_outputs.verify_epub(epub)
    assert any("invalid EPUB XHTML XML" in error for error in errors)


def test_epub_verifier_requires_exact_mathml_manifest_property(tmp_path: Path) -> None:
    missing = tmp_path / "missing-mathml-property.epub"
    _write_minimal_epub(missing, chapter_properties="")
    missing_errors = verify_outputs.verify_epub(missing)
    assert any("contains MathML but does not declare" in error for error in missing_errors)

    false_declaration = tmp_path / "false-mathml-property.epub"
    _write_minimal_epub(
        false_declaration,
        chapter_markup="<p>no equation</p>",
        chapter_properties="mathml",
    )
    false_errors = verify_outputs.verify_epub(false_declaration)
    assert any(
        "declares the mathml property but contains no MathML" in error
        for error in false_errors
    )
