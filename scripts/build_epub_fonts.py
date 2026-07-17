"""Noto CJK에서 EPUB용 한국어 WOFF2 부분집합 글꼴을 만든다."""

from __future__ import annotations

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets/fonts"
SOURCES = {
    "Regular": Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    "Bold": Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
}
SOURCE_SUFFIXES = {".qmd", ".md", ".yml", ".yaml", ".json", ".py", ".js", ".scss", ".css"}
IGNORED_PARTS = {".git", ".quarto", ".tools", ".venv", "_book", "_proof", "_site"}


def required_codepoints() -> set[int]:
    codepoints: set[int] = set()
    for start, end in (
        (0x0020, 0x00FF),  # 기본 라틴 문자와 문장부호
        (0x0370, 0x03FF),  # 그리스 문자
        (0x2000, 0x206F),  # 일반 문장부호
        (0x20A0, 0x20CF),  # 통화 기호
        (0x2100, 0x214F),  # 문자 모양 기호
        (0x2190, 0x21FF),  # 화살표
        (0x2200, 0x22FF),  # 수학 연산자
        (0x2460, 0x24FF),  # 괄호·원 문자
        (0x25A0, 0x26FF),  # 도형과 기타 기호
        (0x3000, 0x303F),  # CJK 문장부호
        (0x3130, 0x318F),  # 한글 호환 자모
        (0xAC00, 0xD7A3),  # 완성형 한글 전체
        (0xFF00, 0xFFEF),  # 전각 문자
    ):
        codepoints.update(range(start, end + 1))

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in SOURCE_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        codepoints.update(map(ord, text))
    return codepoints


def rename_font(font, style: str) -> None:
    family = "Atlas Sans KR"
    full_name = f"{family} {style}"
    postscript_name = f"AtlasSansKR-{style}"
    unique_name = f"Robotics Math Atlas; 1.0; {postscript_name}"
    replacements = {
        1: family,
        2: style,
        3: unique_name,
        4: full_name,
        6: postscript_name,
        16: family,
        17: style,
    }
    names = font["name"]
    platforms = {
        (record.platformID, record.platEncID, record.langID)
        for record in names.names
        if record.nameID in replacements
    }
    for name_id, value in replacements.items():
        for platform_id, encoding_id, language_id in platforms:
            names.setName(value, name_id, platform_id, encoding_id, language_id)
    font["OS/2"].usWeightClass = 700 if style == "Bold" else 400


def build_one(source: Path, style: str, codepoints: set[int]) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"원본 Noto 글꼴을 찾을 수 없습니다: {source}")
    collection = TTCollection(source)
    try:
        font = collection.fonts[1]  # Noto Sans CJK KR
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]
        options.notdef_glyph = True
        options.recommended_glyphs = True
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=codepoints)
        subsetter.subset(font)
        rename_font(font, style)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output = OUTPUT_DIR / f"AtlasSansKR-{style}.woff2"
        font.flavor = "woff2"
        font.save(output)
        return output
    finally:
        collection.close()


def main() -> None:
    codepoints = required_codepoints()
    for style, source in SOURCES.items():
        output = build_one(source, style, codepoints)
        print(f"{output.relative_to(ROOT)}: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
