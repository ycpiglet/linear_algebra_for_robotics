"""2R 자코비안의 최소 특잇값과 요시카와 조작성 곡선을 재현한다."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/figures/jacobian-singular-value-manipulability.svg"

L1_M = 0.4
L2_M = 0.3
Q1_DEG = 30.0
Q2_DEG = np.arange(-180.0, 181.0, 1.0, dtype=np.float64)
SINGULAR_Q2_DEG = np.array([-180.0, 0.0, 180.0])
MARK_EVERY = 45


def position_jacobian(q1_rad: float, q2_rad: float) -> np.ndarray:
    """베이스 프레임에서 표현한 2R 말단 위치 자코비안을 반환한다."""
    s1 = np.sin(q1_rad)
    c1 = np.cos(q1_rad)
    s12 = np.sin(q1_rad + q2_rad)
    c12 = np.cos(q1_rad + q2_rad)
    return np.array(
        [
            [-L1_M * s1 - L2_M * s12, -L2_M * s12],
            [L1_M * c1 + L2_M * c12, L2_M * c12],
        ],
        dtype=np.float64,
    )


def compute_metrics() -> tuple[np.ndarray, np.ndarray]:
    """각 q2에서 최소 특잇값과 |det J|를 계산하고 수학적 불변식을 검사한다."""
    q1_rad = np.deg2rad(Q1_DEG)
    q2_rad = np.deg2rad(Q2_DEG)
    sigma_min = np.empty_like(q2_rad)
    sigma_max = np.empty_like(q2_rad)
    manipulability = np.empty_like(q2_rad)

    for index, angle_rad in enumerate(q2_rad):
        jacobian = position_jacobian(q1_rad, float(angle_rad))
        singular_values = np.linalg.svd(jacobian, compute_uv=False)
        sigma_max[index], sigma_min[index] = singular_values
        manipulability[index] = abs(np.linalg.det(jacobian))

    sigma_min[np.abs(sigma_min) < 1.0e-14] = 0.0
    manipulability[np.abs(manipulability) < 1.0e-14] = 0.0

    expected_manipulability = L1_M * L2_M * np.abs(np.sin(q2_rad))
    np.testing.assert_allclose(manipulability, expected_manipulability, atol=1.0e-14)
    np.testing.assert_allclose(
        manipulability,
        sigma_max * sigma_min,
        rtol=1.0e-12,
        atol=1.0e-14,
    )

    singular_indices = np.searchsorted(Q2_DEG, SINGULAR_Q2_DEG)
    np.testing.assert_allclose(sigma_min[singular_indices], 0.0, atol=1.0e-14)
    np.testing.assert_allclose(manipulability[singular_indices], 0.0, atol=1.0e-14)
    np.testing.assert_allclose(
        manipulability[np.searchsorted(Q2_DEG, [-90.0, 90.0])],
        L1_M * L2_M,
        atol=1.0e-14,
    )
    np.testing.assert_allclose(
        sigma_min[np.searchsorted(Q2_DEG, 60.0)],
        0.15753461,
        rtol=1.0e-7,
    )
    return sigma_min, manipulability


def inject_accessibility(svg_text: str) -> str:
    """SVG 루트에 접근성 역할과 고정 title/desc를 삽입한다."""
    start = svg_text.index("<svg")
    end = svg_text.index(">", start)
    opening = svg_text[start:end]
    opening += (
        ' role="img" '
        'aria-labelledby="jacobian-sv-manip-title jacobian-sv-manip-desc"'
    )
    title_and_description = (
        "\n  <title id=\"jacobian-sv-manip-title\">"
        "2R 자코비안의 최소 특잇값과 요시카와 조작성 연속 곡선"
        "</title>\n"
        "  <desc id=\"jacobian-sv-manip-desc\">"
        "첫째 관절각 30도, 링크 길이 0.4미터와 0.3미터인 2R 평면팔에서 "
        "둘째 관절각을 마이너스 180도부터 180도까지 1도 간격으로 바꾼다. "
        "위 패널의 최소 특잇값과 아래 패널의 요시카와 조작성 절댓값은 "
        "마이너스 180도, 0도, 180도에서 모두 0이 되어 특이점을 표시한다."
        "</desc>"
    )
    return (
        svg_text[:start]
        + opening
        + ">"
        + title_and_description
        + svg_text[end + 1 :]
    )


def style_axis(axis: plt.Axes) -> None:
    axis.set_facecolor("#fbfcfe")
    axis.grid(True, color="#d7dfeb", linewidth=0.8, alpha=0.9)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#5b6578")
    axis.tick_params(colors="#34415a")
    for angle_deg in SINGULAR_Q2_DEG:
        axis.axvline(
            angle_deg,
            color="#a92f49",
            linewidth=1.1,
            linestyle=":",
            alpha=0.7,
            zorder=1,
        )


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Noto Sans CJK KR",
            "svg.fonttype": "none",
            "svg.hashsalt": "jacobian-singular-value-manipulability-v1",
            "axes.unicode_minus": False,
        }
    )
    sigma_min, manipulability = compute_metrics()
    singular_indices = np.searchsorted(Q2_DEG, SINGULAR_Q2_DEG)

    figure, (axis_sigma, axis_manip) = plt.subplots(
        2,
        1,
        figsize=(11.2, 7.8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.0, 1.0], "hspace": 0.25},
    )
    figure.patch.set_facecolor("#fbfcfe")
    style_axis(axis_sigma)
    style_axis(axis_manip)

    axis_sigma.plot(
        Q2_DEG,
        sigma_min,
        color="#087f78",
        linewidth=2.7,
        linestyle="-",
        marker="o",
        markevery=MARK_EVERY,
        markersize=4.8,
        markerfacecolor="#fbfcfe",
        markeredgewidth=1.4,
        label="최소 특잇값 σ_min",
        zorder=3,
    )
    axis_sigma.scatter(
        SINGULAR_Q2_DEG,
        sigma_min[singular_indices],
        color="#a92f49",
        marker="X",
        s=76,
        label="특이점",
        zorder=4,
    )
    axis_sigma.set_ylabel("최소 특잇값 σ_min (m/rad)")
    axis_sigma.set_ylim(bottom=-0.01)
    axis_sigma.set_title(
        "A · 가장 만들기 어려운 순간 속도 방향의 이득",
        loc="left",
        weight="bold",
    )
    axis_sigma.legend(frameon=False, ncol=2, loc="upper center")
    axis_sigma.annotate(
        "펴짐 특이점\nq2=0°",
        xy=(0.0, 0.0),
        xytext=(24.0, 0.055),
        color="#8d253c",
        fontsize=9.5,
        arrowprops={"arrowstyle": "->", "color": "#a92f49", "lw": 1.1},
    )

    axis_manip.plot(
        Q2_DEG,
        manipulability,
        color="#b65c00",
        linewidth=2.7,
        linestyle="--",
        marker="D",
        markevery=MARK_EVERY,
        markersize=4.6,
        markerfacecolor="#fff7e8",
        markeredgewidth=1.2,
        label="요시카와 조작성 w=|det J|",
        zorder=3,
    )
    axis_manip.scatter(
        SINGULAR_Q2_DEG,
        manipulability[singular_indices],
        color="#a92f49",
        marker="X",
        s=76,
        label="특이점",
        zorder=4,
    )
    axis_manip.set_xlabel("둘째 관절각 q2 (°)")
    axis_manip.set_ylabel("조작성 w (m²/rad²)")
    axis_manip.set_ylim(bottom=-0.006)
    axis_manip.set_xticks(np.arange(-180.0, 181.0, 45.0))
    axis_manip.set_title(
        "B · 단위 관절속도 원이 만드는 속도 타원의 면적 척도",
        loc="left",
        weight="bold",
    )
    axis_manip.legend(frameon=False, ncol=2, loc="upper center")

    figure.suptitle(
        "2R 팔은 펴지거나 완전히 접힐 때 두 조작성 지표가 함께 0이 된다",
        x=0.07,
        y=0.982,
        ha="left",
        fontsize=16,
        weight="bold",
        color="#172033",
    )
    figure.text(
        0.07,
        0.018,
        (
            "고정 입력 · l1=0.4 m · l2=0.3 m · q1=30° · "
            "q2=-180°…180° · 간격 1° · NumPy float64 · 무작위수 없음"
        ),
        fontsize=9,
        color="#5b6578",
    )
    figure.subplots_adjust(left=0.11, right=0.98, top=0.90, bottom=0.11)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        OUTPUT,
        format="svg",
        facecolor=figure.get_facecolor(),
        metadata={
            "Date": None,
            "Creator": "Robotics Math Atlas deterministic generator",
        },
    )
    plt.close(figure)
    svg_text = OUTPUT.read_text(encoding="utf-8")
    OUTPUT.write_text(inject_accessibility(svg_text), encoding="utf-8")

    print(
        f"w_max={np.max(manipulability):.6f} m²/rad² · "
        f"sigma_min(q2=60°)="
        f"{sigma_min[np.searchsorted(Q2_DEG, 60.0)]:.8f} m/rad · "
        f"samples={Q2_DEG.size}"
    )


if __name__ == "__main__":
    main()
