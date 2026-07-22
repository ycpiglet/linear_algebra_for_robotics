"""Regression tests for the Atlas authoring and rendering contracts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]


def test_web_theme_uses_shared_tokens_and_content_blocks() -> None:
    theme = (ROOT / "assets/styles/theme.scss").read_text(encoding="utf-8")
    tokens = (ROOT / "assets/styles/_tokens.scss").read_text(encoding="utf-8")
    blocks = (ROOT / "assets/styles/_content-blocks.scss").read_text(encoding="utf-8")

    assert '@import "tokens";' in theme
    assert '@import "content-blocks";' in theme
    for token in (
        "--atlas-type-body-family",
        "--atlas-type-heading-weight",
        "--atlas-type-caption-size",
        "--atlas-type-label-size",
        "--atlas-type-code-family",
        "--atlas-type-math-family",
        "--atlas-leading-body",
        "--atlas-tracking-body",
        "--atlas-paragraph-gap",
        "--atlas-media-gap",
        "--atlas-space-4",
        "--atlas-duration-standard",
    ):
        assert token in tokens
    for selector in (
        ".concept-hero",
        ".key-takeaway",
        ".formula-card",
        ".mistake-card",
        ".page-glossary",
        ".concept-scorecard",
        ".derivation-step",
        ".simulation-placeholder",
        ".reader-tools",
        ".type-role-specimen",
    ):
        assert selector in blocks


def test_type_roles_keep_aliases_use_real_weights_and_define_every_local_token() -> None:
    paths = (
        ROOT / "assets/styles/_tokens.scss",
        ROOT / "assets/styles/theme.scss",
        ROOT / "assets/styles/_content-blocks.scss",
        ROOT / "assets/styles/epub.css",
    )
    tokens, theme, blocks, epub = (path.read_text(encoding="utf-8") for path in paths)
    combined = "\n".join((tokens, theme, blocks, epub))

    for alias, role in (
        ("--atlas-font-body", "--atlas-type-body-family"),
        ("--atlas-font-mono", "--atlas-type-code-family"),
        ("--atlas-font-size-body", "--atlas-type-body-size"),
        ("--atlas-leading-body", "--atlas-type-body-leading"),
        ("--atlas-leading-compact", "--atlas-type-caption-leading"),
        ("--atlas-tracking-body", "--atlas-type-body-tracking"),
        ("--atlas-tracking-heading", "--atlas-type-heading-tracking"),
    ):
        assert f"{alias}: var({role});" in tokens

    definitions = set(re.findall(r"(--atlas-[a-z0-9-]+)\s*:", combined))
    usages = set(re.findall(r"var\(\s*(--atlas-[a-z0-9-]+)", combined))
    assert usages <= definitions

    numeric_weights = {
        int(value)
        for source in (theme, blocks, epub)
        for value in re.findall(r"font-weight:\s*([1-9]\d{2})\s*;", source)
    }
    assert numeric_weights == {400, 700}
    assert "$web-font-path: false;" in theme
    assert '$font-family-sans-serif: "Atlas Sans KR"' in theme
    assert 'font-family: "Atlas Sans KR", "Noto Sans KR"' in epub
    assert "font-synthesis: none" in theme
    assert "font-synthesis: none" in epub
    epub_em = epub.split("em {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    assert "font-style: normal" in epub_em
    assert "text-decoration: underline" in epub_em


def test_bundled_fonts_are_deterministic_and_keep_native_web_parity() -> None:
    expected = {
        "AtlasSansKR-Regular.otf": (
            400,
            "105537d3976ffb40686e020bfbe6c95a466701ff24cb1a581d83c424c61fab02",
        ),
        "AtlasSansKR-Bold.otf": (
            700,
            "f7991701f029074bbe2f76394c9c6c4f111cfad2320aed816215270e225cd4b6",
        ),
        "AtlasSansKR-Regular.woff2": (
            400,
            "28afdc16f0161a4092f700a5a58afc9bf44c61a6cf88c8a2e942f89b32e478df",
        ),
        "AtlasSansKR-Bold.woff2": (
            700,
            "eb99fdcbcc1810ea326ee5881a9121180c46bee8e3be6214800c389140081634",
        ),
    }
    required_characters = "가힣Az0Ω∑→∞−"

    for filename, (expected_weight, expected_hash) in expected.items():
        path = ROOT / "assets/fonts" / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
        font = TTFont(path)
        try:
            family_names = {
                record.toUnicode()
                for record in font["name"].names
                if record.nameID in {1, 16}
            }
            assert family_names == {"Atlas Sans KR"}
            assert font["OS/2"].usWeightClass == expected_weight
            assert font.sfntVersion == "OTTO"
            assert "CFF " in font
            assert "glyf" not in font
            assert font["OS/2"].fsType == 0
            cmap = font.getBestCmap()
            assert all(ord(character) in cmap for character in required_characters)
        finally:
            font.close()

    for style in ("Regular", "Bold"):
        native = TTFont(ROOT / "assets/fonts" / f"AtlasSansKR-{style}.otf")
        web = TTFont(ROOT / "assets/fonts" / f"AtlasSansKR-{style}.woff2")
        try:
            assert native.getBestCmap() == web.getBestCmap()
            assert native.getGlyphOrder() == web.getGlyphOrder()
            assert set(native.keys()) == set(web.keys())
            assert native["head"].modified == web["head"].modified
            assert native["OS/2"].usWeightClass == web["OS/2"].usWeightClass
        finally:
            native.close()
            web.close()

    license_text = (ROOT / "assets/fonts/OFL.txt").read_text(encoding="utf-8")
    assert "Copyright 2010-2012 Google Corporation" in license_text
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert "derivatives of Noto Sans CJK KR" in license_text

    builder = (ROOT / "scripts/build_epub_fonts.py").read_text(encoding="utf-8")
    assert "font.recalcTimestamp = False" in builder
    assert "SOURCE_SHA256" in builder
    assert "family_names != {SOURCE_FAMILY}" in builder
    assert '(("otf", None), ("woff2", "woff2"))' in builder
    for ignored in (
        '".pytest_cache"',
        '"_freeze"',
        '"_review"',
        '"__pycache__"',
        '"generated"',
        '"test-results"',
    ):
        assert ignored in builder


def test_type_role_specimen_pdf_adapter_and_real_pilots_are_wired() -> None:
    design = (ROOT / "design-system.qmd").read_text(encoding="utf-8")
    concept = (
        ROOT / "content/concepts/statistics/maximum-likelihood-estimation.qmd"
    ).read_text(encoding="utf-8")
    lab = (ROOT / "courseware/labs/kalman-lab.qmd").read_text(encoding="utf-8")
    book = (ROOT / "_quarto-book.yml").read_text(encoding="utf-8")
    proof = (ROOT / "_quarto-proof.yml").read_text(encoding="utf-8")

    for contract in (
        "#type-role-specimen",
        "body · 긴 설명",
        "heading · 문서 계층",
        "caption · figure",
        "label · 짧은 control",
        "code · 한글 주석",
        "math · inline",
        "금지",
    ):
        assert contract in design
    assert ".concept-hero .type-role-pilot" in concept
    assert "apply_atlas_plot_style()" in lab
    assert "ATLAS_PLOT_COLORS" in lab
    assert "fig-kalman-lab-type-pilot" in lab
    for config in (book, proof):
        assert "font-paths: [assets/fonts]" in config
        assert 'mainfont: "Atlas Sans KR"' in config
        assert 'codefont: "Noto Sans Mono CJK KR"' in config
        assert "include-before-body: assets/styles/typst-fonts.typ" in config

    typst_adapter = (ROOT / "assets/styles/typst-fonts.typ").read_text(encoding="utf-8")
    assert '#set text(font: "Atlas Sans KR")' in typst_adapter
    assert '#show raw: set text(font: "Noto Sans Mono CJK KR")' in typst_adapter
    assert '#show emph: it => text(fill: rgb("#6740a5"), underline(it.body))' in typst_adapter


def test_web_reader_tools_preserve_bookmarks_and_read_position() -> None:
    script = (ROOT / "assets/js/atlas.js").read_text(encoding="utf-8")

    for contract in (
        "bookmarks",
        "favorites",
        "lastRead",
        "data-reader-range",
        "data-reader-bookmark",
        "data-reader-favorite",
        "절 ${sectionIndex + 1}/${currentHeadings.length}",
        "aria-valuetext",
        "pagehide",
        "markUserMovement",
    ):
        assert contract in script

    assert 'max="100"' in script
    assert "Number(range.value) / 100" in script
    assert "window.addEventListener('scroll', () => { userMoved = true; }" not in script


def test_prerequisite_ui_keeps_required_helpful_and_not_required_groups() -> None:
    script = (ROOT / "assets/js/atlas.js").read_text(encoding="utf-8")

    for contract in (
        "PREREQUISITE_CATEGORIES",
        "PLANNED_CONCEPT_LABELS",
        "conceptDisplayName",
        "not_required",
        "필요 없음",
        "확률과정(stochastic process)",
        "역기구학(inverse kinematics)",
        "prerequisite-groups",
        "data-prerequisite-category",
        "prerequisite-item__marker",
        ".filter((group) => group.entries.length)",
    ):
        assert contract in script

    assert "['required', 'helpful'].forEach" not in script
    assert "group.id === 'not_required'" in script
    assert "선수개념 체크리스트 · 별도 준비 없음" in script


def test_optional_reading_time_is_visible_and_accessibly_labelled() -> None:
    script = (ROOT / "assets/js/atlas.js").read_text(encoding="utf-8")

    for contract in (
        "const readingTimeEntries",
        "const makeReadingTime",
        "concept.reading_time",
        'aria-label="예상 읽기 시간"',
        "빠른",
        "핵심",
        "전체",
    ):
        assert contract in script

    assert "if (!entries.length) return '';" in script
    assert "읽기 예상 시간" in script


def test_epub_has_reflow_and_math_contract() -> None:
    config = (ROOT / "_quarto-book.yml").read_text(encoding="utf-8")
    epub = (ROOT / "assets/styles/epub.css").read_text(encoding="utf-8")

    assert "css: assets/styles/epub.css" in config
    assert 'math[display="inline"]' in epub
    assert 'math[display="block"]' in epub
    assert "overflow-x: auto" in epub
    assert "Noto Sans CJK KR" in epub
    assert 'font-family: "Atlas Sans KR"' in epub
    assert "../fonts/AtlasSansKR-Regular.woff2" in epub
    assert "../fonts/AtlasSansKR-Bold.woff2" in epub
    assert (ROOT / "assets/fonts/AtlasSansKR-Regular.woff2").stat().st_size > 100_000
    assert (ROOT / "assets/fonts/AtlasSansKR-Bold.woff2").stat().st_size > 100_000
    assert "SIL OPEN FONT LICENSE" in (
        ROOT / "assets/fonts/OFL.txt"
    ).read_text(encoding="utf-8")
    assert ".quarto-figure figure" in epub
    assert "figcaption" in epub
    dark_rules = epub.split("@media (prefers-color-scheme: dark)", maxsplit=1)[1]
    for selector in (
        ".concept-scorecard",
        ".derivation-step",
        ".simulation-placeholder",
        ".reference-note",
        ".metric-badge",
    ):
        assert selector in dark_rules


def test_output_verifier_checks_epub_package_fonts_math_and_pdf_navigation() -> None:
    verifier = (ROOT / "scripts/verify_outputs.py").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for contract in (
        'infos[0].filename != "mimetype"',
        'container_member = "META-INF/container.xml"',
        '"mathml" in item[2].split()',
        "regular and bold Korean WOFF2 fonts are required",
        'endswith("ofl.txt")',
        "page-glossary--static",
        "def verify_pdf",
        "reader.outline",
        "internal PDF links",
            "embedded Atlas Sans KR PDF styles are missing",
    ):
        assert contract in verifier
    assert '"$$epub" "$$pdf"' in makefile
    assert '_proof "$$pdf"' in makefile


def test_book_contains_all_flagship_chapters_and_reference_pages() -> None:
    config = (ROOT / "_quarto-book.yml").read_text(encoding="utf-8")

    for chapter in (
        "content/concepts/robotics/jacobian.qmd",
        "content/concepts/statistics/maximum-likelihood-estimation.qmd",
        "content/concepts/estimation/kalman-filter.qmd",
        "content/references/jacobian-references.qmd",
        "content/references/maximum-likelihood-estimation-references.qmd",
        "content/references/kalman-filter-references.qmd",
        "future-scope.qmd",
    ):
        assert chapter in config


def test_book_contains_every_concept_source() -> None:
    config = (ROOT / "_quarto-book.yml").read_text(encoding="utf-8")
    configured = set(re.findall(r"-\s+(content/concepts/[^\s]+\.qmd)", config))
    sources = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "content/concepts").rglob("*.qmd")
    }

    assert configured == sources


def test_internal_authoring_sources_are_not_standalone_pages() -> None:
    ignored = (ROOT / ".quartoignore").read_text(encoding="utf-8")
    web = (ROOT / "_quarto-web.yml").read_text(encoding="utf-8")

    for source in (
        "AUTHORING_MANUAL.md",
        "platform/templates/",
        "platform/generated/glossary.qmd",
    ):
        assert source in ignored

    assert 'render:' in web
    assert '- "*.qmd"' in web
    assert '- "content/**/*.qmd"' in web
    assert '- "!platform/**"' in web
    assert 'platform/**/*.qmd' not in web


def test_static_page_glossary_survives_without_javascript() -> None:
    config = (ROOT / "_quarto.yml").read_text(encoding="utf-8")
    page_filter = (
        ROOT / "platform/extension/static-page-glossary.lua"
    ).read_text(encoding="utf-8")
    epub = (ROOT / "assets/styles/epub.css").read_text(encoding="utf-8")
    script = (ROOT / "assets/js/atlas.js").read_text(encoding="utf-8")

    assert "platform/extension/static-page-glossary.lua" in config
    assert '"atlas-term"' in page_filter
    assert '"page-glossary"' in page_filter
    assert "pandoc.DefinitionList" in page_filter
    assert ".page-glossary" in epub
    assert "const existingGlossary" in script
    enhancement = script.index("element.setAttribute('tabindex', '0')")
    early_exit = script.index("if (existingGlossary || !terms.size) return;")
    assert enhancement < early_exit
    assert ".includes(english.toLocaleLowerCase('en'))" in script


def test_web_documents_use_url_independent_dublin_core_identity() -> None:
    config = (ROOT / "_quarto.yml").read_text(encoding="utf-8")
    identity_filter = (
        ROOT / "platform/extension/document-identity.lua"
    ).read_text(encoding="utf-8")
    verifier = (ROOT / "scripts/verify_outputs.py").read_text(encoding="utf-8")

    assert "platform/extension/document-identity.lua" in config
    for contract in (
        'quarto.doc.is_format("html:js")',
        "quarto.doc.input_file",
        "quarto.project.directory",
        "pandoc.path.make_relative",
        'quarto.doc.include_text(',
        'name=\"DC.identifier\"',
        "urn:robotics-math-atlas:document:v1:",
    ):
        assert contract in identity_filter
    for forbidden in ("github.io", "linear_algebra_for_robotics", "/review/", "/preview/"):
        assert forbidden not in identity_filter
    assert "expected exactly one DC.identifier" in verifier
    assert "if document.is_redirect:" in verifier
    assert "duplicate DC.identifier" in verifier
    assert "URL-dependent DC.identifier" in verifier


def test_design_system_renders_operational_block_and_control_specimens() -> None:
    design = (ROOT / "design-system.qmd").read_text(encoding="utf-8")

    for specimen in (
        "{.failure-mode}",
        "{.algorithm-card}",
        "{.tradeoff-card}",
        "reader-tools--specimen",
        "simulation-placeholder__controls",
        "page-glossary--static",
    ):
        assert specimen in design

    assert 'aria-pressed="true"' in design
    assert 'aria-disabled="true"' in design
    assert 'aria-valuetext="42%, 절 3/18, 유도"' in design
    assert 'type="range"' in design
    assert 'disabled="disabled"' in design
    assert not re.search(r"\sdisabled(?:\s|>)", design)
    assert not re.search(r"<input\b(?:(?!/\s*>).)*>", design, flags=re.DOTALL)


def test_common_ui_preserves_mobile_dark_and_keyboard_contracts() -> None:
    blocks = (ROOT / "assets/styles/_content-blocks.scss").read_text(encoding="utf-8")
    theme = (ROOT / "assets/styles/theme.scss").read_text(encoding="utf-8")
    script = (ROOT / "assets/js/atlas.js").read_text(encoding="utf-8")

    mobile = blocks.split("@media (max-width: 36rem)", maxsplit=1)[1]
    for selector in (
        ".concept-toolbar__reading-time",
        ".concept-toolbar__reading-time-list",
        ".prerequisite-group__heading",
        ".reader-tools",
    ):
        assert selector in mobile

    assert "body.quarto-dark" in theme
    assert "overflow-x: clip" in theme
    assert ":focus-visible" in theme
    assert "var(--atlas-surface)" in blocks
    assert "var(--atlas-ink)" in blocks
    for shortcut in ("event.key.toLowerCase() === 'f'", "=== 'b'", "=== 't'"):
        assert shortcut in script
    for shortcut in ('aria-keyshortcuts="Alt+F"', 'Alt+B', 'Alt+T'):
        assert shortcut in script
    assert 'data-reader-bookmark aria-pressed="false"' in script
    assert 'data-reader-range aria-label="이 페이지 읽기 위치"' in script


def test_representative_chapter_exercises_the_design_language() -> None:
    pilot = (
        ROOT
        / "content/concepts/statistics/maximum-likelihood-estimation.qmd"
    ).read_text(encoding="utf-8")

    for block in (
        "concept-hero",
        "key-takeaway",
        "learning-objectives",
        "term-card",
        "formula-card",
        "assumption-box",
        "engineering-meaning",
        "failure-mode",
        "mistake-card",
        "history-card",
        "depth-derivation",
        "depth-proof",
    ):
        assert f"{{.{block}" in pilot
    assert '<abbr title="Maximum Likelihood Estimation">MLE</abbr>' in pilot
    assert "## 24. 한 장짜리 실무 보고 양식" in pilot


def test_prose_math_is_not_accidentally_formatted_as_code() -> None:
    accidental_code_math = re.compile(r"`\$[^`\n]+\$`")
    failures: list[str] = []
    for source in sorted(ROOT.rglob("*.qmd")):
        if any(part.startswith("_") for part in source.relative_to(ROOT).parts):
            continue
        text = source.read_text(encoding="utf-8")
        for match in accidental_code_math.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            failures.append(f"{source.relative_to(ROOT)}:{line}: {match.group(0)}")
    assert not failures, "math wrapped in inline code:\n" + "\n".join(failures)
