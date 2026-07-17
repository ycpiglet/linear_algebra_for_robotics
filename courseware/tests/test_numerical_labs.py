from __future__ import annotations

import numpy as np
import pytest

from robotics_math_atlas import (
    bootstrap_particle_filter,
    constant_velocity_kalman,
    least_squares_line,
    random_walk_metropolis,
    simulate_pid,
    systematic_resample,
)


def test_least_squares_residual_is_orthogonal_to_design() -> None:
    x = np.linspace(-2.0, 3.0, 20)
    y = 1.25 - 0.4 * x + 0.1 * np.sin(x)
    result = least_squares_line(x, y)

    assert result["rank"] == 2
    assert np.linalg.norm(result["design"].T @ result["residual"]) < 1e-10


def test_pid_reduces_error_and_respects_saturation() -> None:
    result = simulate_pid(output_limit=0.8, duration=8.0)

    assert abs(result["error"][-1]) < abs(result["error"][0])
    assert np.max(np.abs(result["control"])) <= 0.8 + 1e-12


def test_kalman_covariance_is_symmetric_psd_and_improves_rmse() -> None:
    result = constant_velocity_kalman(steps=180)

    for covariance in result["covariances"]:
        assert np.allclose(covariance, covariance.T, atol=1e-12)
        assert np.linalg.eigvalsh(covariance).min() >= -1e-12
    assert result["estimate_rmse"] < result["measurement_rmse"]


def test_systematic_resampling_returns_valid_ancestors() -> None:
    rng = np.random.default_rng(3)
    indices = systematic_resample([0.05, 0.15, 0.3, 0.5], rng)

    assert indices.shape == (4,)
    assert np.all((indices >= 0) & (indices < 4))
    assert np.all(indices[:-1] <= indices[1:])


def test_particle_filter_outputs_finite_diagnostics() -> None:
    observations = np.linspace(0.0, 5.0, 12)
    result = bootstrap_particle_filter(observations, particles=400)

    assert np.isfinite(result["estimates"]).all()
    assert np.all(result["effective_sample_size"] >= 1.0 - 1e-10)
    assert np.all(result["effective_sample_size"] <= 400.0 + 1e-10)


def test_random_walk_metropolis_recovers_standard_normal_moments() -> None:
    result = random_walk_metropolis(
        lambda value: -0.5 * value**2,
        proposal_std=1.0,
        draws=20_000,
        burn_in=2_000,
        seed=101,
    )

    assert result["acceptance_rate"] == pytest.approx(0.7, abs=0.08)
    assert result["mean"] == pytest.approx(0.0, abs=0.08)
    assert result["variance"] == pytest.approx(1.0, abs=0.1)


@pytest.mark.parametrize(
    ("function", "kwargs"),
    [
        (simulate_pid, {"dt": 0.0}),
        (constant_velocity_kalman, {"measurement_std": 0.0}),
    ],
)
def test_invalid_parameters_are_rejected(function, kwargs) -> None:
    with pytest.raises(ValueError):
        function(**kwargs)
