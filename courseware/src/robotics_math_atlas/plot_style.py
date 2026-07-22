"""Matplotlib adapter for the Atlas semantic type and color roles."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import matplotlib as mpl
from matplotlib import font_manager

_ROOT = Path(__file__).resolve().parents[3]
_ATLAS_FONT_PATHS = (
    _ROOT / "assets/fonts/AtlasSansKR-Regular.otf",
    _ROOT / "assets/fonts/AtlasSansKR-Bold.otf",
)
_ATLAS_FONTS_REGISTERED = False


def _register_atlas_fonts() -> None:
    """Register the repository-owned native faces for this process."""

    global _ATLAS_FONTS_REGISTERED
    if _ATLAS_FONTS_REGISTERED:
        return
    for path in _ATLAS_FONT_PATHS:
        if not path.is_file():
            raise FileNotFoundError(
                "Atlas plot styling requires the repository-owned font assets; "
                f"missing: {path}"
            )
        font_manager.fontManager.addfont(path)
    _ATLAS_FONTS_REGISTERED = True

# _tokens.scss is canonical. These native Matplotlib values are deliberately
# duplicated because Matplotlib cannot consume CSS custom properties; parity
# is enforced by the design-contract tests.
ATLAS_PLOT_COLORS: Mapping[str, str] = MappingProxyType(
    {
        "ink": "#172033",
        "ink_soft": "#34415a",
        "muted": "#5b6578",
        "canvas": "#fbfcfe",
        "surface": "#ffffff",
        "line": "#d7dfeb",
        "blue": "#1459b8",
        "teal": "#087f78",
        "coral": "#a92f49",
        "amber": "#955000",
        "violet": "#6740ad",
        "green": "#217a4c",
    }
)

ATLAS_PLOT_TYPE: Mapping[str, object] = MappingProxyType(
    {
        "body_family": "Atlas Sans KR",
        "body_weight": 400,
        "body_size_pt": 10,
        "heading_weight": 700,
        "heading_size_pt": 15,
        "caption_weight": 400,
        "caption_size_pt": 9,
        "label_weight": 700,
        "label_size_pt": 9,
    }
)


def atlas_plot_rc() -> dict[str, object]:
    """Return a fresh rcParams mapping for a light, static Atlas figure."""

    colors = ATLAS_PLOT_COLORS
    type_roles = ATLAS_PLOT_TYPE
    return {
        "font.family": type_roles["body_family"],
        "font.size": type_roles["body_size_pt"],
        "font.weight": type_roles["body_weight"],
        "text.color": colors["ink"],
        "axes.titlecolor": colors["ink"],
        "axes.titlesize": type_roles["heading_size_pt"],
        "axes.titleweight": type_roles["heading_weight"],
        "axes.labelcolor": colors["ink_soft"],
        "axes.labelsize": type_roles["label_size_pt"],
        "axes.labelweight": type_roles["label_weight"],
        "axes.edgecolor": colors["line"],
        "axes.facecolor": colors["surface"],
        "axes.prop_cycle": mpl.cycler(
            color=(
                colors["blue"],
                colors["teal"],
                colors["coral"],
                colors["amber"],
                colors["violet"],
                colors["green"],
            )
        ),
        "figure.facecolor": colors["surface"],
        "legend.fontsize": type_roles["caption_size_pt"],
        "legend.labelcolor": colors["ink_soft"],
        "xtick.color": colors["muted"],
        "ytick.color": colors["muted"],
        "xtick.labelsize": type_roles["caption_size_pt"],
        "ytick.labelsize": type_roles["caption_size_pt"],
        "grid.color": colors["line"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }


def apply_atlas_plot_style() -> None:
    """Apply the Atlas role mapping to Matplotlib's current process."""

    _register_atlas_fonts()
    mpl.rcParams.update(atlas_plot_rc())
