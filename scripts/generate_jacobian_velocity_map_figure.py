"""자코비안 열의 순간 효과와 말단속도 가중합 그림을 재생성한다.

기존 수작업 SVG(assets/figures/jacobian-2r-velocity-map.svg)의 라벨 겹침을
없애기 위해 같은 수치를 matplotlib으로 다시 그린다. 상수는 본문 §9의
수치 예제와 동일하다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/figures/jacobian-2r-velocity-map.svg"

L1_M = 0.4
L2_M = 0.3
Q1_DEG = 30.0
Q2_DEG = 60.0
QDOT_RAD_S = np.array([0.5, -0.2])

INK = "#172033"
MUTED = "#5b6578"
CANVAS = "#fbfcfe"
LINK = "#34415a"
BLUE = "#1459b8"
CORAL = "#a92f49"
TEAL = "#087f78"


def jacobian_columns() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """관절 2·말단 위치와 자코비안 두 열, 말단속도를 계산·검증한다."""
    q1 = np.deg2rad(Q1_DEG)
    q12 = np.deg2rad(Q1_DEG + Q2_DEG)
    joint2 = np.array([L1_M * np.cos(q1), L1_M * np.sin(q1)])
    tip = joint2 + np.array([L2_M * np.cos(q12), L2_M * np.sin(q12)])
    jacobian = np.array(
        [
            [-L1_M * np.sin(q1) - L2_M * np.sin(q12), -L2_M * np.sin(q12)],
            [L1_M * np.cos(q1) + L2_M * np.cos(q12), L2_M * np.cos(q12)],
        ]
    )
    tip_velocity = jacobian @ QDOT_RAD_S
    np.testing.assert_allclose(
        tip_velocity,
        QDOT_RAD_S[0] * jacobian[:, 0] + QDOT_RAD_S[1] * jacobian[:, 1],
        rtol=0,
        atol=1e-15,
    )
    return joint2, tip, jacobian, tip_velocity


def draw_arrow(axis, start, vector, color, linewidth=2.4, zorder=4):
    axis.annotate(
        "",
        xy=(start[0] + vector[0], start[1] + vector[1]),
        xytext=(start[0], start[1]),
        arrowprops={"arrowstyle": "-|>", "color": color,
                    "linewidth": linewidth, "shrinkA": 0, "shrinkB": 0},
        zorder=zorder,
    )


def inject_accessibility(svg_text: str) -> str:
    """SVG 루트에 접근성 역할과 고정 title/desc를 삽입한다."""
    start = svg_text.index("<svg")
    end = svg_text.index(">", start)
    opening = svg_text[start:end]
    opening += (
        ' role="img" aria-labelledby="jacobian-velocity-map-title jacobian-velocity-map-desc"'
    )
    title_and_description = (
        "\n  <title id=\"jacobian-velocity-map-title\">"
        "자코비안 열의 순간 효과와 말단속도의 가중합"
        "</title>\n"
        "  <desc id=\"jacobian-velocity-map-desc\">"
        "왼쪽 패널은 관절각 30도와 60도로 굽힌 2R 팔의 말단에서 자코비안 첫째 열 "
        "(-0.500, 0.346)과 둘째 열 (-0.300, 0)을 화살표로 보인다. 오른쪽 패널은 "
        "관절속도 0.5와 -0.2 라디안 매 초로 두 열을 가중해 머리-꼬리로 이으면 "
        "말단속도 (-0.190, 0.173) 미터 매 초가 됨을 평행사변형으로 보인다."
        "</desc>"
    )
    return (svg_text[:start] + opening + svg_text[end:end + 1]
            + title_and_description + svg_text[end + 1:])


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Noto Sans CJK KR",
            "svg.fonttype": "none",
            "svg.hashsalt": "jacobian-2r-velocity-map-v2",
            "axes.unicode_minus": False,
        }
    )
    joint2, tip, jacobian, tip_velocity = jacobian_columns()
    j1, j2 = jacobian[:, 0], jacobian[:, 1]
    origin = np.array([0.0, 0.0])

    figure, (axis_pose, axis_sum) = plt.subplots(1, 2, figsize=(11.6, 5.6))
    figure.patch.set_facecolor(CANVAS)
    for axis in (axis_pose, axis_sum):
        axis.set_facecolor(CANVAS)
        axis.set_aspect("equal")
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_color("#d7dfeb")

    # --- 패널 A: 자세와 두 열 ---
    axis_pose.set_title("A · 현재 자세와 자코비안 두 열", loc="left",
                        fontsize=12.5, color=INK, pad=10)
    for start, endpoint in ((origin, joint2), (joint2, tip)):
        axis_pose.plot([start[0], endpoint[0]], [start[1], endpoint[1]],
                       color=LINK, linewidth=6.0, solid_capstyle="round", zorder=2)
    axis_pose.scatter(*origin, s=110, color=CANVAS, edgecolor=INK, linewidth=1.6, zorder=3)
    axis_pose.scatter(*joint2, s=110, color=CANVAS, edgecolor=INK, linewidth=1.6, zorder=3)
    axis_pose.scatter(*tip, s=70, color=INK, zorder=3)

    draw_arrow(axis_pose, tip, j1, CORAL)
    draw_arrow(axis_pose, tip, j2, BLUE)
    # j1은 왼쪽 위, j2는 왼쪽 아래로 뻗는다 — 라벨은 화살표 끝 반대편 여백에 둔다.
    axis_pose.text(tip[0] + j1[0] - 0.02, tip[1] + j1[1] + 0.03,
                   "j₁ = (-0.500, 0.346)", color=CORAL, fontsize=10.5, ha="left")
    axis_pose.text(tip[0] + j2[0] - 0.02, tip[1] + j2[1] - 0.055,
                   "j₂ = (-0.300, 0)", color=BLUE, fontsize=10.5, ha="left")
    axis_pose.text(0.16, -0.075, "q₁=30°, q₂=60°", color=MUTED, fontsize=10)
    axis_pose.text(-0.62, -0.19,
                   "빨강 j₁: 관절 1만 1 rad/s · 파랑 j₂: 관절 2만 1 rad/s일 때의 말단속도",
                   color=MUTED, fontsize=9.3)
    axis_pose.set_xlim(-0.66, 0.78)
    axis_pose.set_ylim(-0.24, 0.95)

    # --- 패널 B: 가중합 ---
    axis_sum.set_title("B · q̇ 성분으로 가중해 더하기", loc="left",
                       fontsize=12.5, color=INK, pad=10)
    v1 = QDOT_RAD_S[0] * j1
    v2 = QDOT_RAD_S[1] * j2
    draw_arrow(axis_sum, origin, v1, CORAL)
    draw_arrow(axis_sum, v1, v2, BLUE)
    draw_arrow(axis_sum, origin, tip_velocity, TEAL, linewidth=3.2, zorder=5)
    # 평행사변형 보조선
    axis_sum.plot([v2[0], tip_velocity[0]], [v2[1], tip_velocity[1]],
                  color=MUTED, linewidth=1.0, linestyle="--", zorder=1)
    axis_sum.plot([0, v2[0]], [0, v2[1]], color=MUTED, linewidth=1.0,
                  linestyle="--", zorder=1)

    axis_sum.text(v1[0] * 0.5 - 0.02, v1[1] * 0.5 - 0.042, "0.5 j₁",
                  color=CORAL, fontsize=10.5, ha="center")
    axis_sum.text(v1[0] + v2[0] * 0.5, v1[1] + 0.022, "-0.2 j₂",
                  color=BLUE, fontsize=10.5, ha="center", va="bottom")
    axis_sum.text(tip_velocity[0] + 0.01, tip_velocity[1] + 0.068,
                  "ṗ = (-0.190, 0.173) m/s", color=TEAL, fontsize=11,
                  ha="center", fontweight="bold")
    axis_sum.text(-0.31, -0.115, "q̇₁ = 0.5 rad/s,  q̇₂ = -0.2 rad/s",
                  color=MUTED, fontsize=10)
    axis_sum.text(-0.31, -0.165, "ṗ = j₁q̇₁ + j₂q̇₂ = J(q)q̇",
                  color=INK, fontsize=10.5)
    axis_sum.set_xlim(-0.34, 0.16)
    axis_sum.set_ylim(-0.20, 0.36)

    figure.suptitle("자코비안의 열은 관절 하나의 순간 효과이고, 말단속도는 그 가중합이다",
                    x=0.02, ha="left", fontsize=13.5, color=INK)
    figure.tight_layout(rect=(0, 0, 1, 0.94))

    figure.savefig(OUTPUT, format="svg", bbox_inches="tight", facecolor=CANVAS)
    plt.close(figure)
    svg_text = OUTPUT.read_text(encoding="utf-8")
    OUTPUT.write_text(inject_accessibility(svg_text), encoding="utf-8")
    print(
        f"j1=({j1[0]:.3f}, {j1[1]:.3f}) · j2=({j2[0]:.3f}, {j2[1]:.3f}) · "
        f"pdot=({tip_velocity[0]:.3f}, {tip_velocity[1]:.3f}) m/s"
    )


if __name__ == "__main__":
    main()
