from __future__ import annotations

import io
import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager

from robotics_math_atlas.plot_style import (
    ATLAS_PLOT_COLORS,
    ATLAS_PLOT_TYPE,
    apply_atlas_plot_style,
)

ROOT = Path(__file__).resolve().parents[2]


def test_plot_adapter_registers_only_repository_atlas_faces() -> None:
    apply_atlas_plot_style()
    for style, weight in (("Regular", 400), ("Bold", 700)):
        selected = Path(
            font_manager.findfont(
                font_manager.FontProperties(family="Atlas Sans KR", weight=weight),
                fallback_to_default=False,
            )
        ).resolve()
        assert selected == (ROOT / f"assets/fonts/AtlasSansKR-{style}.otf").resolve()


def test_plot_adapter_matches_canonical_color_and_weight_tokens() -> None:
    tokens = (ROOT / "assets/styles/_tokens.scss").read_text(encoding="utf-8")
    light_tokens = tokens.split(".quarto-dark", maxsplit=1)[0]
    canonical_colors = {
        name.replace("-", "_"): value.casefold()
        for name, value in re.findall(
            r"--atlas-([a-z-]+):\s*(#[0-9a-fA-F]{6});",
            light_tokens,
        )
    }

    for role, value in ATLAS_PLOT_COLORS.items():
        assert value.casefold() == canonical_colors[role]
    assert ATLAS_PLOT_TYPE["body_weight"] == 400
    assert ATLAS_PLOT_TYPE["caption_weight"] == 400
    assert ATLAS_PLOT_TYPE["heading_weight"] == 700
    assert ATLAS_PLOT_TYPE["label_weight"] == 700


def test_plot_adapter_preserves_mixed_text_as_svg_text() -> None:
    with mpl.rc_context():
        apply_atlas_plot_style()
        figure, axis = plt.subplots(figsize=(4, 2.5))
        axis.set_title("한글 Atlas Ω → ∑")
        axis.set_xlabel("시간 time [s]")
        axis.plot([0, 1], [0, 1], label="추정 estimate")
        axis.legend()
        output = io.StringIO()
        figure.savefig(output, format="svg")
        plt.close(figure)

    svg = output.getvalue()
    assert "한글 Atlas Ω → ∑" in svg
    assert "시간 time [s]" in svg
    assert "추정 estimate" in svg
    assert "Atlas Sans KR" in svg
    assert "Noto Sans CJK KR" not in svg
