"""Minimal MCMC kernels whose invariance arguments are developed in the proof text."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray


def random_walk_metropolis(
    log_density: Callable[[float], float],
    *,
    initial: float = 0.0,
    proposal_std: float = 1.0,
    draws: int = 12_000,
    burn_in: int = 2_000,
    seed: int = 23,
) -> dict[str, NDArray[np.float64] | float]:
    """Sample a scalar target with symmetric Gaussian random-walk Metropolis."""

    if proposal_std <= 0 or draws <= 0 or burn_in < 0:
        raise ValueError("proposal_std and draws must be positive; burn_in must be nonnegative")
    rng = np.random.default_rng(seed)
    total = draws + burn_in
    chain = np.empty(total)
    accepted = np.zeros(total, dtype=bool)
    current = float(initial)
    current_log_density = float(log_density(current))

    for index in range(total):
        proposal = current + rng.normal(0.0, proposal_std)
        proposal_log_density = float(log_density(proposal))
        log_acceptance_ratio = min(0.0, proposal_log_density - current_log_density)
        if np.log(rng.random()) < log_acceptance_ratio:
            current = proposal
            current_log_density = proposal_log_density
            accepted[index] = True
        chain[index] = current

    retained = chain[burn_in:]
    return {
        "samples": retained,
        "full_chain": chain,
        "accepted": accepted,
        "acceptance_rate": float(np.mean(accepted)),
        "mean": float(np.mean(retained)),
        "variance": float(np.var(retained, ddof=1)),
    }

