"""Build deterministic native Atlas OTF faces for repository-owned figures.

The source TTC files are supplied by the pinned Ubuntu Noto CJK package.  They
are intentionally not accepted by filename alone: the bytes, collection face,
family, outline format, and weight must all match before an output is written.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection, TTFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets/fonts"
SOURCE_FAMILY = "Noto Sans CJK KR"
TARGET_FAMILY = "Atlas Sans KR"
TTC_FACE_INDEX = 1


@dataclass(frozen=True)
class FontSource:
    style: str
    weight: int
    path: Path
    sha256: str


SOURCES = (
    FontSource(
        style="Regular",
        weight=400,
        path=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        sha256="b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a",
    ),
    FontSource(
        style="Bold",
        weight=700,
        path=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        sha256="faa5f3656a78b2e2d450d27fe8382c778bc2b6bb5ea29c986664a6a435056ceb",
    ),
)

# Only these generators consume the native faces in PUB-006.  Reading their
# labels supplements the fixed Korean/Latin/math coverage without allowing
# unrelated build output or checkout-local files to change the font bytes.
FIGURE_GENERATORS = (
    Path("scripts/generate_jacobian_2r_geometry_figure.py"),
    Path("scripts/generate_jacobian_velocity_map_figure.py"),
    Path("scripts/generate_jacobian_singularity_curve.py"),
    Path("scripts/generate_kalman_tuning_figure.py"),
)

UNICODE_RANGES = (
    (0x0020, 0x00FF),  # Basic Latin, Latin-1, punctuation, degree sign
    (0x0370, 0x03FF),  # Greek
    (0x2000, 0x209F),  # General punctuation and superscripts/subscripts
    (0x20A0, 0x20CF),  # Currency symbols
    (0x2100, 0x214F),  # Letterlike symbols
    (0x2190, 0x22FF),  # Arrows and mathematical operators
    (0x2460, 0x26FF),  # Enclosed characters, shapes, miscellaneous symbols
    (0x3000, 0x303F),  # CJK punctuation
    (0x3130, 0x318F),  # Hangul compatibility jamo
    (0xAC00, 0xD7A3),  # All modern Hangul syllables
    (0xFF00, 0xFFEF),  # Full-width forms
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _font_names(font: TTFont, name_ids: set[int]) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID in name_ids
    }


def required_codepoints(root: Path = ROOT) -> set[int]:
    """Return the stable glyph contract for the four managed generators."""

    codepoints: set[int] = set()
    for start, end in UNICODE_RANGES:
        codepoints.update(range(start, end + 1))
    for relative_path in FIGURE_GENERATORS:
        source = root / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"figure generator is missing: {source}")
        codepoints.update(map(ord, source.read_text(encoding="utf-8")))
    return codepoints


def validate_source(source: FontSource) -> TTCollection:
    """Open and validate one exact Noto CJK source collection."""

    if not source.path.is_file():
        raise FileNotFoundError(f"pinned Noto CJK source is missing: {source.path}")
    actual_sha256 = _sha256(source.path)
    if actual_sha256 != source.sha256:
        raise ValueError(
            f"pinned Noto CJK source hash mismatch for {source.path}: "
            f"expected {source.sha256}, got {actual_sha256}"
        )

    collection = TTCollection(source.path)
    try:
        if len(collection.fonts) <= TTC_FACE_INDEX:
            raise ValueError(
                f"TTC face index {TTC_FACE_INDEX} is unavailable in {source.path}"
            )
        font = collection.fonts[TTC_FACE_INDEX]
        family_names = _font_names(font, {1, 16})
        if family_names != {SOURCE_FAMILY}:
            raise ValueError(
                f"TTC face {TTC_FACE_INDEX} family mismatch for {source.path}: "
                f"expected {SOURCE_FAMILY!r}, got {sorted(family_names)!r}"
            )
        actual_weight = int(font["OS/2"].usWeightClass)
        if actual_weight != source.weight:
            raise ValueError(
                f"TTC face {TTC_FACE_INDEX} weight mismatch for {source.path}: "
                f"expected {source.weight}, got {actual_weight}"
            )
        if font.sfntVersion != "OTTO":
            raise ValueError(
                f"TTC face {TTC_FACE_INDEX} is not a native CFF/OTF face: "
                f"{font.sfntVersion!r}"
            )
    except Exception:
        collection.close()
        raise
    return collection


def rename_font(font: TTFont, source: FontSource) -> None:
    """Give the subset its repository-owned family and weight metadata."""

    full_name = f"{TARGET_FAMILY} {source.style}"
    postscript_name = f"AtlasSansKR-{source.style}"
    replacements = {
        1: TARGET_FAMILY,
        2: source.style,
        3: f"Robotics Math Atlas; 1.0; {postscript_name}",
        4: full_name,
        6: postscript_name,
        16: TARGET_FAMILY,
        17: source.style,
    }
    names = font["name"]
    platforms = {
        (record.platformID, record.platEncID, record.langID)
        for record in names.names
        if record.nameID in replacements
    }
    for name_id, value in replacements.items():
        for platform_id, encoding_id, language_id in sorted(platforms):
            names.setName(value, name_id, platform_id, encoding_id, language_id)
    font["OS/2"].usWeightClass = source.weight

    cff = font["CFF "].cff
    cff.fontNames = [postscript_name]
    top_dict = cff.topDictIndex[0]
    top_dict.FullName = full_name
    top_dict.FamilyName = TARGET_FAMILY
    top_dict.Weight = source.style


def validate_output(path: Path, source: FontSource, codepoints: set[int]) -> None:
    """Verify family, weight, CFF outlines, and glyph coverage after writing."""

    with TTFont(path, recalcTimestamp=False) as font:
        if font.sfntVersion != "OTTO":
            raise ValueError(f"native output is not OTF/CFF: {path}")
        family_names = _font_names(font, {1, 16})
        if family_names != {TARGET_FAMILY}:
            raise ValueError(
                f"output family mismatch for {path}: {sorted(family_names)!r}"
            )
        actual_weight = int(font["OS/2"].usWeightClass)
        if actual_weight != source.weight:
            raise ValueError(
                f"output weight mismatch for {path}: "
                f"expected {source.weight}, got {actual_weight}"
            )
        postscript_name = f"AtlasSansKR-{source.style}"
        cff = font["CFF "].cff
        top_dict = cff.topDictIndex[0]
        if cff.fontNames != [postscript_name]:
            raise ValueError(f"output CFF name mismatch for {path}: {cff.fontNames!r}")
        if (top_dict.FullName, top_dict.FamilyName, top_dict.Weight) != (
            f"{TARGET_FAMILY} {source.style}",
            TARGET_FAMILY,
            source.style,
        ):
            raise ValueError(f"output CFF metadata mismatch for {path}")
        missing = codepoints - set(font.getBestCmap())
        if missing:
            preview = ", ".join(f"U+{value:04X}" for value in sorted(missing)[:8])
            raise ValueError(f"output glyph coverage mismatch for {path}: {preview}")


def build_one(
    source: FontSource,
    codepoints: set[int],
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Build one deterministic native OTF face."""

    collection = validate_source(source)
    try:
        font = collection.fonts[TTC_FACE_INDEX]
        supported_codepoints = codepoints & set(font.getBestCmap())
        if not supported_codepoints:
            raise ValueError(f"source face has no requested glyphs: {source.path}")
        # FontTools otherwise replaces head.modified with wall-clock time.
        font.recalcTimestamp = False
        options = subset.Options()
        options.layout_features = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]
        options.notdef_glyph = True
        options.recommended_glyphs = True
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=sorted(supported_codepoints))
        subsetter.subset(font)
        rename_font(font, source)

        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"AtlasSansKR-{source.style}.otf"
        font.flavor = None
        font.save(output, reorderTables=True)
        output.chmod(0o644)
    finally:
        collection.close()

    validate_output(output, source, supported_codepoints)
    return output


def main() -> None:
    codepoints = required_codepoints()
    for source in SOURCES:
        output = build_one(source, codepoints)
        print(
            f"{output.relative_to(ROOT)}: {output.stat().st_size:,} bytes · "
            f"sha256={_sha256(output)}"
        )


if __name__ == "__main__":
    main()
