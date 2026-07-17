"""Kalman and particle-filter experiments with deterministic random seeds."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def constant_velocity_kalman(
    *,
    steps: int = 160,
    dt: float = 0.1,
    acceleration_std: float = 0.35,
    measurement_std: float = 1.2,
    seed: int = 11,
) -> dict[str, NDArray[np.float64] | float]:
    """Simulate and estimate 1-D position/velocity with a linear Kalman filter."""

    if steps < 2 or dt <= 0 or acceleration_std < 0 or measurement_std <= 0:
        raise ValueError("invalid simulation parameters")

    rng = np.random.default_rng(seed)
    transition = np.array([[1.0, dt], [0.0, 1.0]])
    control = np.array([0.5 * dt**2, dt])
    observation = np.array([[1.0, 0.0]])
    process_covariance = acceleration_std**2 * np.outer(control, control)
    measurement_covariance = np.array([[measurement_std**2]])

    truth = np.zeros((steps, 2))
    measurements = np.zeros(steps)
    estimates = np.zeros((steps, 2))
    covariances = np.zeros((steps, 2, 2))
    innovations = np.zeros(steps)
    gains = np.zeros((steps, 2))
    covariance = np.diag([4.0, 2.0])
    state = np.array([0.0, 0.0])
    truth[0] = np.array([0.0, 0.7])
    covariances[0] = covariance

    for index in range(1, steps):
        commanded_acceleration = 0.35 * np.sin(index * dt * 0.7)
        noisy_acceleration = commanded_acceleration + rng.normal(0.0, acceleration_std)
        truth[index] = transition @ truth[index - 1] + control * noisy_acceleration
        measurements[index] = truth[index, 0] + rng.normal(0.0, measurement_std)

        predicted_state = transition @ state + control * commanded_acceleration
        predicted_covariance = transition @ covariance @ transition.T + process_covariance
        innovation = measurements[index] - (observation @ predicted_state).item()
        innovation_covariance = (
            observation @ predicted_covariance @ observation.T
        ).item() + measurement_std**2
        gain = (predicted_covariance @ observation.T / innovation_covariance).reshape(-1)
        state = predicted_state + gain * innovation

        # Joseph form preserves symmetry and positive semidefiniteness better numerically.
        identity = np.eye(2)
        correction = identity - np.outer(gain, observation.reshape(-1))
        covariance = (
            correction @ predicted_covariance @ correction.T
            + np.outer(gain, gain) * measurement_covariance[0, 0]
        )
        covariance = 0.5 * (covariance + covariance.T)

        estimates[index] = state
        covariances[index] = covariance
        innovations[index] = innovation
        gains[index] = gain

    rmse_measurement = float(np.sqrt(np.mean((measurements[1:] - truth[1:, 0]) ** 2)))
    rmse_estimate = float(np.sqrt(np.mean((estimates[1:, 0] - truth[1:, 0]) ** 2)))
    return {
        "time": np.arange(steps) * dt,
        "truth": truth,
        "measurements": measurements,
        "estimates": estimates,
        "covariances": covariances,
        "innovations": innovations,
        "gains": gains,
        "measurement_rmse": rmse_measurement,
        "estimate_rmse": rmse_estimate,
    }


def systematic_resample(weights: ArrayLike, rng: np.random.Generator) -> NDArray[np.int64]:
    """Draw ancestor indices using systematic resampling."""

    normalized = np.asarray(weights, dtype=float).reshape(-1)
    if normalized.size == 0 or np.any(normalized < 0) or not np.isfinite(normalized).all():
        raise ValueError("weights must be a non-empty, finite, nonnegative vector")
    total = float(normalized.sum())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    normalized = normalized / total
    cumulative = np.cumsum(normalized)
    cumulative[-1] = 1.0
    positions = (rng.random() + np.arange(normalized.size)) / normalized.size
    return np.searchsorted(cumulative, positions, side="right").astype(np.int64)


def bootstrap_particle_filter(
    observations: ArrayLike,
    *,
    particles: int = 1_500,
    process_std: float = 1.0,
    measurement_std: float = 1.0,
    resample_threshold: float = 0.5,
    seed: int = 19,
) -> dict[str, NDArray[np.float64] | float]:
    """Bootstrap particle filter for the classic nonlinear state-space benchmark.

    State transition:
    ``x_t = 0.5*x + 25*x/(1+x^2) + 8*cos(1.2*t) + noise``.
    Observation: ``y_t = x_t^2/20 + noise``.
    """

    values = np.asarray(observations, dtype=float).reshape(-1)
    if particles < 2 or process_std <= 0 or measurement_std <= 0:
        raise ValueError("invalid particle-filter parameters")
    if not 0 < resample_threshold <= 1:
        raise ValueError("resample_threshold must lie in (0, 1]")

    rng = np.random.default_rng(seed)
    cloud = rng.normal(0.0, 5.0, size=particles)
    weights = np.full(particles, 1.0 / particles)
    estimates = np.zeros(values.size)
    effective_size = np.zeros(values.size)
    resampled = np.zeros(values.size, dtype=bool)
    snapshots = np.zeros((values.size, min(particles, 250)))

    for index, measurement in enumerate(values):
        time = index + 1
        cloud = (
            0.5 * cloud
            + 25.0 * cloud / (1.0 + cloud**2)
            + 8.0 * np.cos(1.2 * time)
            + rng.normal(0.0, process_std, size=particles)
        )
        residual = measurement - cloud**2 / 20.0
        log_weights = -0.5 * (residual / measurement_std) ** 2
        log_weights -= np.max(log_weights)
        weights = np.exp(log_weights)
        total = float(weights.sum())
        weights = weights / total if total > 0 else np.full(particles, 1.0 / particles)
        estimates[index] = float(weights @ cloud)
        effective_size[index] = 1.0 / float(weights @ weights)
        snapshots[index] = cloud[: snapshots.shape[1]]

        if effective_size[index] < resample_threshold * particles:
            ancestors = systematic_resample(weights, rng)
            cloud = cloud[ancestors]
            weights.fill(1.0 / particles)
            resampled[index] = True

    return {
        "estimates": estimates,
        "effective_sample_size": effective_size,
        "resampled": resampled,
        "particle_snapshots": snapshots,
        "resampling_rate": float(np.mean(resampled)),
    }
