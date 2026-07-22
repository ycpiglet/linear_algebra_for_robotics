"""Register the repository-owned Atlas OTF faces with Matplotlib on demand."""

from __future__ import annotations

from pathlib import Path

from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
ATLAS_FONT_FAMILY = "Atlas Sans KR"
ATLAS_FONT_PATHS = {
    400: ROOT / "assets/fonts/AtlasSansKR-Regular.otf",
    700: ROOT / "assets/fonts/AtlasSansKR-Bold.otf",
}
SVG_METADATA = {
    "Date": None,
    "Creator": "Robotics Math Atlas deterministic generator",
}

_registered = False


def register_atlas_fonts() -> None:
    """Lazily register the exact repository files for this Python process."""

    global _registered
    if _registered:
        return
    for weight, path in ATLAS_FONT_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(
                f"Atlas Sans KR weight {weight} is missing from the repository: {path}"
            )
        font_manager.fontManager.addfont(path)
    _registered = True


def stabilize_svg_text(svg_text: str) -> str:
    """Remove backend formatting noise while preserving SVG semantics."""

    return "\n".join(line.rstrip(" \t") for line in svg_text.splitlines()) + "\n"
