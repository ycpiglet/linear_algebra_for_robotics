"""Small, inspectable linear-algebra experiments used by the textbook."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def least_squares_line(x: ArrayLike, y: ArrayLike) -> dict[str, NDArray[np.float64] | float]:
    """Fit ``y ≈ intercept + slope*x`` with a numerically stable QR/SVD backend.

    The function deliberately calls :func:`numpy.linalg.lstsq` rather than forming
    ``(A.T @ A)^{-1}``, so the lab can compare the mathematics of the normal equations
    with a safer implementation.
    """

    x_values = np.asarray(x, dtype=float).reshape(-1)
    y_values = np.asarray(y, dtype=float).reshape(-1)
    if x_values.size != y_values.size:
        raise ValueError("x and y must contain the same number of samples")
    if x_values.size < 2:
        raise ValueError("at least two samples are required")
    if not (np.isfinite(x_values).all() and np.isfinite(y_values).all()):
        raise ValueError("x and y must be finite")

    design = np.column_stack((np.ones_like(x_values), x_values))
    coefficients, _, rank, singular_values = np.linalg.lstsq(design, y_values, rcond=None)
    fitted = design @ coefficients
    residual = y_values - fitted
    condition = float(
        np.inf if singular_values[-1] == 0 else singular_values[0] / singular_values[-1]
    )
    return {
        "coefficients": coefficients,
        "design": design,
        "fitted": fitted,
        "residual": residual,
        "residual_norm": float(np.linalg.norm(residual)),
        "rank": float(rank),
        "condition": condition,
    }
