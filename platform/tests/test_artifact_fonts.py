from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from fontTools.ttLib import TTFont
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import atlas_matplotlib_fonts  # noqa: E402
import build_atlas_native_fonts  # noqa: E402

EXPECTED_FONTS = {
    400: (
        ROOT / "assets/fonts/AtlasSansKR-Regular.otf",
        "4a4cc415f918e44a73c3f3b8614d582d909ccc3af651bc2fdc79de8d09f11818",
    ),
    700: (
        ROOT / "assets/fonts/AtlasSansKR-Bold.otf",
        "b8432223280a4a3261978a4c90a1e01687e476157388ebd9e1e03053d76eeabc",
    ),
}
GENERATORS = (
    "scripts/generate_jacobian_2r_geometry_figure.py",
    "scripts/generate_jacobian_velocity_map_figure.py",
    "scripts/generate_jacobian_singularity_curve.py",
    "scripts/generate_kalman_tuning_figure.py",
)
SHARED_SOURCES = {
    "scripts/atlas_matplotlib_fonts.py",
    "scripts/build_atlas_native_fonts.py",
    "assets/fonts/AtlasSansKR-Regular.otf",
    "assets/fonts/AtlasSansKR-Bold.otf",
}
GENERATED_OUTPUTS = (
    "assets/figures/jacobian-2r-geometry.svg",
    "assets/figures/jacobian-2r-velocity-map.svg",
    "assets/figures/jacobian-singular-value-manipulability.svg",
    "assets/figures/kalman-prior-and-tuning-comparison.svg",
)


def test_native_fonts_have_pinned_bytes_metadata_and_figure_glyphs() -> None:
    required = build_atlas_native_fonts.required_codepoints()
    for weight, (path, expected_hash) in EXPECTED_FONTS.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
        with TTFont(path, recalcTimestamp=False) as font:
            cmap = set(font.getBestCmap())
            assert font.sfntVersion == "OTTO"
            assert font["OS/2"].usWeightClass == weight
            assert {
                record.toUnicode()
                for record in font["name"].names
                if record.nameID in {1, 16}
            } == {"Atlas Sans KR"}
            cff = font["CFF "].cff
            style = "Regular" if weight == 400 else "Bold"
            top_dict = cff.topDictIndex[0]
            assert cff.fontNames == [f"AtlasSansKR-{style}"]
            assert (top_dict.FullName, top_dict.FamilyName, top_dict.Weight) == (
                f"Atlas Sans KR {style}",
                "Atlas Sans KR",
                style,
            )
            assert set(range(0xAC00, 0xD7A4)) <= cmap
            assert set(map(ord, "로봇 자코비안 칼만 σν√")) <= cmap
            assert len(required & cmap) > 12_000


def test_generated_svg_text_is_fully_covered_by_repository_fonts() -> None:
    cmaps: list[set[int]] = []
    for path, _ in EXPECTED_FONTS.values():
        with TTFont(path, recalcTimestamp=False) as font:
            cmaps.append(set(font.getBestCmap()))
    common_cmap = set.intersection(*cmaps)

    for relative_path in GENERATED_OUTPUTS:
        output_path = ROOT / relative_path
        output_bytes = output_path.read_bytes()
        assert b"<dc:date>" not in output_bytes
        assert not any(line.endswith((b" ", b"\t")) for line in output_bytes.splitlines())
        root = ET.fromstring(output_bytes)
        text_codepoints = {
            ord(character)
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == "text"
            for character in "".join(element.itertext())
            if not character.isspace()
        }
        assert text_codepoints <= common_cmap


def test_matplotlib_resolves_both_weights_to_repository_otf() -> None:
    atlas_matplotlib_fonts.register_atlas_fonts()
    for weight, (path, _) in EXPECTED_FONTS.items():
        resolved = font_manager.findfont(
            font_manager.FontProperties(family=["Atlas Sans KR"], weight=weight),
            fallback_to_default=False,
        )
        assert Path(resolved).resolve() == path.resolve()


def test_all_generated_figures_use_and_manifest_the_repository_fonts() -> None:
    manifest = yaml.safe_load((ROOT / "assets/artifact-manifest.yml").read_text(encoding="utf-8"))
    generated = {
        artifact["generator"]["command"][1]: set(artifact["sources"])
        for artifact in manifest["artifacts"]
        if artifact["production"] == "generated"
    }
    assert set(generated) == set(GENERATORS)
    for generator, sources in generated.items():
        text = (ROOT / generator).read_text(encoding="utf-8")
        assert "register_atlas_fonts()" in text
        assert '"font.family": ATLAS_FONT_FAMILY' in text
        assert "Noto Sans CJK" not in text
        assert sources >= SHARED_SOURCES


def test_native_font_builder_pins_source_hash_family_face_and_weights() -> None:
    assert build_atlas_native_fonts.SOURCE_FAMILY == "Noto Sans CJK KR"
    assert build_atlas_native_fonts.TARGET_FAMILY == "Atlas Sans KR"
    assert build_atlas_native_fonts.TTC_FACE_INDEX == 1
    assert {
        source.style: (source.weight, source.sha256)
        for source in build_atlas_native_fonts.SOURCES
    } == {
        "Regular": (
            400,
            "b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a",
        ),
        "Bold": (
            700,
            "faa5f3656a78b2e2d450d27fe8382c778bc2b6bb5ea29c986664a6a435056ceb",
        ),
    }
