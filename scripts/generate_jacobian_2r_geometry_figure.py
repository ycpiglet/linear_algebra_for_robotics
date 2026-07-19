"""2R 평면팔의 기하(링크·관절각·말단)를 본문 상수 그대로 그린다.

본문 §3의 텍스트 다이어그램을 대체한다. 링크 길이와 관절각은
generate_jacobian_singularity_curve.py와 동일한 상수를 쓴다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/figures/jacobian-2r-geometry.svg"

L1_M = 0.4
L2_M = 0.3
Q1_DEG = 30.0
Q2_DEG = 60.0

INK = "#172033"
MUTED = "#5b6578"
CANVAS = "#fbfcfe"
LINK = "#34415a"
BLUE = "#1459b8"
TEAL = "#087f78"
AMBER = "#955000"


def forward_kinematics() -> tuple[np.ndarray, np.ndarray]:
    """관절 2와 말단의 위치를 계산하고 폐형식과 대조한다."""
    q1 = np.deg2rad(Q1_DEG)
    q12 = np.deg2rad(Q1_DEG + Q2_DEG)
    joint2 = np.array([L1_M * np.cos(q1), L1_M * np.sin(q1)])
    tip = joint2 + np.array([L2_M * np.cos(q12), L2_M * np.sin(q12)])
    np.testing.assert_allclose(
        tip,
        [L1_M * np.cos(q1) + L2_M * np.cos(q12), L1_M * np.sin(q1) + L2_M * np.sin(q12)],
        rtol=0,
        atol=1e-15,
    )
    return joint2, tip


def inject_accessibility(svg_text: str) -> str:
    """SVG 루트에 접근성 역할과 고정 title/desc를 삽입한다."""
    start = svg_text.index("<svg")
    end = svg_text.index(">", start)
    opening = svg_text[start:end]
    opening += (
        ' role="img" aria-labelledby="jacobian-2r-geometry-title jacobian-2r-geometry-desc"'
    )
    title_and_description = (
        "\n  <title id=\"jacobian-2r-geometry-title\">"
        "2R 평면팔의 기하 정의"
        "</title>\n"
        "  <desc id=\"jacobian-2r-geometry-desc\">"
        "기준좌표계 0의 원점에서 길이 0.4미터인 링크 1이 관절각 30도로 뻗어 관절 2에 닿고, "
        "길이 0.3미터인 링크 2가 링크 1에 대한 상대각 60도로 이어져 말단 p에 닿는다. "
        "관절각 q1은 x축에서, q2는 링크 1의 연장선에서 잰다."
        "</desc>"
    )
    return (svg_text[:start] + opening + svg_text[end:end + 1]
            + title_and_description + svg_text[end + 1:])


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Noto Sans CJK KR",
            "svg.fonttype": "none",
            "svg.hashsalt": "jacobian-2r-geometry-v1",
            "axes.unicode_minus": False,
        }
    )
    joint2, tip = forward_kinematics()
    origin = np.array([0.0, 0.0])

    figure, axis = plt.subplots(figsize=(7.8, 6.2))
    figure.patch.set_facecolor(CANVAS)
    axis.set_facecolor(CANVAS)
    axis.set_aspect("equal")
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_xticks([])
    axis.set_yticks([])

    # 기준좌표계 축
    axis.annotate("", xy=(0.62, 0.0), xytext=(-0.10, 0.0),
                  arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.4})
    axis.annotate("", xy=(0.0, 0.62), xytext=(0.0, -0.08),
                  arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.4})
    axis.text(0.63, -0.015, "x", color=MUTED, fontsize=12, va="top")
    axis.text(-0.018, 0.63, "y", color=MUTED, fontsize=12, ha="right")
    axis.text(0.03, -0.055, "기준좌표계 {0} 원점", color=MUTED, fontsize=10.5, ha="left")

    # 링크와 관절
    for start, endpoint in ((origin, joint2), (joint2, tip)):
        axis.plot([start[0], endpoint[0]], [start[1], endpoint[1]],
                  color=LINK, linewidth=6.5, solid_capstyle="round", zorder=2)
    axis.scatter(*origin, s=140, color=CANVAS, edgecolor=INK, linewidth=1.8, zorder=3)
    axis.scatter(*joint2, s=140, color=CANVAS, edgecolor=INK, linewidth=1.8, zorder=3)
    axis.scatter(*tip, s=90, color=AMBER, edgecolor=INK, linewidth=1.2, zorder=3)

    # 링크 1의 연장선(상대각 q2의 기준선)
    extension = joint2 + 0.17 * (joint2 - origin) / np.linalg.norm(joint2 - origin)
    axis.plot([joint2[0], extension[0]], [joint2[1], extension[1]],
              color=MUTED, linewidth=1.1, linestyle=":", zorder=1)

    # 관절각 호
    axis.add_patch(Arc(origin, 0.24, 0.24, angle=0.0, theta1=0.0, theta2=Q1_DEG,
                       color=BLUE, linewidth=1.8, zorder=2))
    axis.text(0.145, 0.033, "q₁", color=BLUE, fontsize=12.5, fontweight="bold")
    axis.add_patch(Arc(joint2, 0.20, 0.20, angle=Q1_DEG, theta1=0.0, theta2=Q2_DEG,
                       color=TEAL, linewidth=1.8, zorder=2))
    axis.text(joint2[0] + 0.115, joint2[1] + 0.085, "q₂", color=TEAL,
              fontsize=12.5, fontweight="bold")

    # 링크·말단 라벨 (링크에서 수직으로 띄워 겹침 방지)
    mid1 = 0.5 * (origin + joint2)
    axis.text(mid1[0] + 0.028, mid1[1] - 0.045, "l₁ = 0.4 m", color=INK, fontsize=11.5)
    mid2 = 0.5 * (joint2 + tip)
    axis.text(mid2[0] + 0.028, mid2[1], "l₂ = 0.3 m", color=INK, fontsize=11.5)
    axis.text(joint2[0] + 0.04, joint2[1] - 0.025, "관절 2", color=INK,
              fontsize=10.5, ha="left", va="top")
    axis.text(tip[0] + 0.035, tip[1] + 0.012, "말단 p = (x, y)", color=INK,
              fontsize=11.5, ha="left")
    axis.text(joint2[0] + 0.175, joint2[1] + 0.033,
              "q₂는 링크 1에 대한 상대각", color=MUTED, fontsize=10, ha="left")

    axis.set_xlim(-0.16, 0.95)
    axis.set_ylim(-0.12, 0.68)
    axis.set_title("2R 평면팔의 기하: 두 회전관절과 링크 길이", loc="left",
                   fontsize=13.5, color=INK, pad=12)

    figure.savefig(OUTPUT, format="svg", bbox_inches="tight", facecolor=CANVAS)
    plt.close(figure)
    svg_text = OUTPUT.read_text(encoding="utf-8")
    OUTPUT.write_text(inject_accessibility(svg_text), encoding="utf-8")
    print(f"joint2=({joint2[0]:.4f}, {joint2[1]:.4f}) m · tip=({tip[0]:.4f}, {tip[1]:.4f}) m")


if __name__ == "__main__":
    main()
