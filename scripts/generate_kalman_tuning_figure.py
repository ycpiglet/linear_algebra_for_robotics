"""칼만 필터 조정 비교 그림을 재현한다."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/figures/kalman-prior-and-tuning-comparison.svg"

DT_S = 0.1
N_STEPS = 121
SEED = 20260716
R_BASE_M2 = 0.25
Q_DENSITY_M2_S3 = 0.20


def make_truth() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = np.arange(N_STEPS, dtype=float) * DT_S
    acceleration_m_s2 = np.zeros(N_STEPS)
    acceleration_m_s2[(time_s >= 3.0) & (time_s < 5.0)] = 0.8
    acceleration_m_s2[(time_s >= 8.0) & (time_s < 9.0)] = -0.6

    position_m = np.zeros(N_STEPS)
    velocity_m_s = np.zeros(N_STEPS)
    for k in range(1, N_STEPS):
        a = acceleration_m_s2[k - 1]
        position_m[k] = (
            position_m[k - 1]
            + velocity_m_s[k - 1] * DT_S
            + 0.5 * a * DT_S**2
        )
        velocity_m_s[k] = velocity_m_s[k - 1] + a * DT_S
    return time_s, position_m, velocity_m_s


def process_covariance(scale: float) -> np.ndarray:
    dt = DT_S
    return scale * Q_DENSITY_M2_S3 * np.array(
        [[dt**3 / 3.0, dt**2 / 2.0], [dt**2 / 2.0, dt]],
        dtype=float,
    )


def run_filter(
    measurements_m: np.ndarray,
    *,
    q_scale: float,
    r_scale: float,
) -> dict[str, np.ndarray | float]:
    F = np.array([[1.0, DT_S], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = process_covariance(q_scale)
    R = np.array([[R_BASE_M2 * r_scale]])
    x = np.array([0.0, 0.0])
    P = np.diag([1.0, 0.5])

    priors_m = np.empty(N_STEPS)
    posteriors_m = np.empty(N_STEPS)
    normalized_innovations = np.empty(N_STEPS)
    nis = np.empty(N_STEPS)

    for k, z_m in enumerate(measurements_m):
        if k > 0:
            x = F @ x
            P = F @ P @ F.T + Q
        priors_m[k] = x[0]

        innovation = np.array([z_m]) - H @ x
        S = H @ P @ H.T + R
        PHt = P @ H.T
        K = np.linalg.solve(S, PHt.T).T
        x = x + K @ innovation
        A = np.eye(2) - K @ H
        P = A @ P @ A.T + K @ R @ K.T
        P = 0.5 * (P + P.T)

        posteriors_m[k] = x[0]
        normalized_innovations[k] = innovation[0] / np.sqrt(S[0, 0])
        nis[k] = innovation @ np.linalg.solve(S, innovation)

    return {
        "prior_m": priors_m,
        "posterior_m": posteriors_m,
        "normalized_innovation": normalized_innovations,
        "nis": nis,
    }


def inject_accessibility(svg_text: str) -> str:
    start = svg_text.index("<svg")
    end = svg_text.index(">", start)
    opening = svg_text[start:end]
    opening += ' role="img" aria-labelledby="kalman-tuning-title kalman-tuning-desc"'
    title = (
        "\n  <title id=\"kalman-tuning-title\">"
        "예측과 보정을 구분하고 잘못된 Q와 R의 혁신을 비교한다"
        "</title>\n"
        "  <desc id=\"kalman-tuning-desc\">"
        "위 그래프는 합성 이동 궤적, 잡음 측정, 측정 직전 예측, 측정 후 추정을 보여 준다. "
        "아래 그래프는 같은 자료에서 기준 설정, 너무 작은 과정 잡음 Q, 너무 작은 측정 잡음 R의 "
        "정규화 혁신을 비교하며 플러스 마이너스 3 기준선을 표시한다."
        "</desc>"
    )
    return svg_text[:start] + opening + ">" + title + svg_text[end + 1 :]


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Noto Sans CJK KR",
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
        }
    )
    time_s, truth_m, _ = make_truth()
    rng = np.random.default_rng(SEED)
    measurements_m = truth_m + rng.normal(0.0, np.sqrt(R_BASE_M2), N_STEPS)

    settings = {
        "기준 Q, R": (1.0, 1.0, "#1459b8", "-", "o"),
        "Q를 100배 작게": (0.01, 1.0, "#b65c00", "--", "^"),
        "R을 100배 작게": (1.0, 0.01, "#a92f49", ":", "x"),
    }
    results = {
        label: run_filter(measurements_m, q_scale=q_scale, r_scale=r_scale)
        for label, (q_scale, r_scale, _, _, _) in settings.items()
    }

    figure, (axis_top, axis_bottom) = plt.subplots(
        2,
        1,
        figsize=(11.2, 7.8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.18, 1.0], "hspace": 0.24},
    )
    figure.patch.set_facecolor("#fbfcfe")
    for axis in (axis_top, axis_bottom):
        axis.set_facecolor("#fbfcfe")
        axis.grid(True, color="#d7dfeb", linewidth=0.8, alpha=0.9)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#5b6578")

    baseline = results["기준 Q, R"]
    axis_top.plot(time_s, truth_m, color="#172033", linewidth=2.6, label="참 위치")
    axis_top.scatter(
        time_s[::2],
        measurements_m[::2],
        color="#6d778a",
        s=18,
        alpha=0.62,
        label="위치 측정",
        zorder=2,
    )
    axis_top.plot(
        time_s,
        baseline["prior_m"],
        color="#087f78",
        linewidth=2.0,
        linestyle="--",
        label="측정 직전 사전 예측",
    )
    axis_top.plot(
        time_s,
        baseline["posterior_m"],
        color="#1459b8",
        linewidth=2.8,
        label="측정 후 사후 추정",
    )
    axis_top.set_ylabel("위치 (m)")
    axis_top.set_title(
        "A · 같은 시각에도 사전 예측과 사후 추정은 다르다",
        loc="left",
        weight="bold",
    )
    axis_top.legend(ncol=2, frameon=False, loc="upper left")

    for label, (_, _, color, linestyle, marker) in settings.items():
        result = results[label]
        axis_bottom.plot(
            time_s,
            result["normalized_innovation"],
            color=color,
            linewidth=1.8,
            linestyle=linestyle,
            marker=marker,
            markevery=12,
            markersize=4.6,
            label=label,
        )
    axis_bottom.axhline(3.0, color="#34415a", linewidth=1.2, linestyle="--")
    axis_bottom.axhline(-3.0, color="#34415a", linewidth=1.2, linestyle="--")
    axis_bottom.fill_between(time_s, -3.0, 3.0, color="#b8c5d9", alpha=0.14)
    axis_bottom.set_ylim(-12.0, 12.0)
    axis_bottom.set_xlabel("시간 (s)")
    axis_bottom.set_ylabel("정규화 혁신 ν/√S")
    axis_bottom.set_title(
        "B · Q 또는 R을 과소평가하면 같은 잔차도 예상 범위를 반복해서 벗어난다",
        loc="left",
        weight="bold",
    )
    axis_bottom.legend(ncol=3, frameon=False, loc="upper left")
    axis_bottom.text(
        12.0,
        3.35,
        "+3 기준",
        ha="right",
        va="bottom",
        color="#34415a",
        fontsize=9,
    )

    figure.suptitle(
        "예측을 따로 그리면 지연이 보이고, 혁신을 정규화하면 잘못된 공분산이 보인다",
        x=0.07,
        y=0.985,
        ha="left",
        fontsize=16,
        weight="bold",
        color="#172033",
    )
    figure.text(
        0.07,
        0.008,
        (
            f"교육용 합성 자료 · Δt={DT_S:.1f} s · 위치 측정분산 R={R_BASE_M2:.2f} m² · "
            f"난수 씨앗={SEED} · Q/R 배율만 변경"
        ),
        fontsize=9,
        color="#5b6578",
    )
    figure.subplots_adjust(left=0.09, right=0.98, top=0.91, bottom=0.10)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    OUTPUT.write_text(inject_accessibility(OUTPUT.read_text(encoding="utf-8")), encoding="utf-8")

    for label, result in results.items():
        rmse_m = float(np.sqrt(np.mean((result["posterior_m"] - truth_m) ** 2)))
        nis_mean = float(np.mean(result["nis"]))
        outside_3sigma_pct = float(
            100.0 * np.mean(np.abs(result["normalized_innovation"]) > 3.0)
        )
        print(
            f"{label}: RMSE={rmse_m:.4f} m, "
            f"mean NIS={nis_mean:.3f}, |ν|/√S>3={outside_3sigma_pct:.1f}%"
        )


if __name__ == "__main__":
    main()
