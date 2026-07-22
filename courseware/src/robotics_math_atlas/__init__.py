"""Reproducible numerical experiments for Robotics Math Atlas."""

from .estimation import (
    bootstrap_particle_filter,
    constant_velocity_kalman,
    systematic_resample,
)
from .linear_algebra import least_squares_line
from .mcmc import random_walk_metropolis
from .pid import simulate_pid

__all__ = [
    "bootstrap_particle_filter",
    "constant_velocity_kalman",
    "least_squares_line",
    "random_walk_metropolis",
    "simulate_pid",
    "systematic_resample",
]
