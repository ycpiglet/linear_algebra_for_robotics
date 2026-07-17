"""Transparent PID simulations with explicit assumptions."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def simulate_pid(
    *,
    kp: float = 2.0,
    ki: float = 0.8,
    kd: float = 0.2,
    setpoint: float = 1.0,
    plant_gain: float = 1.0,
    time_constant: float = 0.7,
    dt: float = 0.01,
    duration: float = 6.0,
    output_limit: float = 5.0,
    derivative_filter: float = 0.12,
    measurement_noise: float = 0.0,
    seed: int = 7,
) -> dict[str, NDArray[np.float64]]:
    """Simulate a PID-controlled first-order plant.

    Plant assumption: ``tau * dx/dt + x = plant_gain * u``. The derivative is
    taken on the measured output (derivative kick avoidance), then low-pass filtered.
    Conditional integration prevents additional wind-up while the actuator saturates.
    """

    if dt <= 0 or duration <= 0 or time_constant <= 0:
        raise ValueError("dt, duration, and time_constant must be positive")
    if output_limit <= 0:
        raise ValueError("output_limit must be positive")
    if not 0 <= derivative_filter <= 1:
        raise ValueError("derivative_filter must lie in [0, 1]")

    time = np.arange(0.0, duration + 0.5 * dt, dt)
    output = np.zeros_like(time)
    control = np.zeros_like(time)
    error = np.zeros_like(time)
    proportional = np.zeros_like(time)
    integral_term = np.zeros_like(time)
    derivative_term = np.zeros_like(time)
    rng = np.random.default_rng(seed)
    integral_state = 0.0
    derivative_state = 0.0
    previous_measurement = output[0]

    for index in range(1, time.size):
        measurement = output[index - 1] + rng.normal(0.0, measurement_noise)
        current_error = setpoint - measurement
        raw_derivative = -(measurement - previous_measurement) / dt
        derivative_state = (
            derivative_filter * raw_derivative + (1.0 - derivative_filter) * derivative_state
        )

        candidate_integral = integral_state + current_error * dt
        p_value = kp * current_error
        d_value = kd * derivative_state
        raw_control = p_value + ki * candidate_integral + d_value
        saturated = float(np.clip(raw_control, -output_limit, output_limit))

        drives_further_into_saturation = (raw_control > output_limit and current_error > 0) or (
            raw_control < -output_limit and current_error < 0
        )
        if not drives_further_into_saturation:
            integral_state = candidate_integral
            raw_control = p_value + ki * integral_state + d_value
            saturated = float(np.clip(raw_control, -output_limit, output_limit))

        derivative = (-output[index - 1] + plant_gain * saturated) / time_constant
        output[index] = output[index - 1] + dt * derivative
        control[index] = saturated
        error[index] = current_error
        proportional[index] = p_value
        integral_term[index] = ki * integral_state
        derivative_term[index] = d_value
        previous_measurement = measurement

    error[0] = setpoint - output[0]
    return {
        "time": time,
        "setpoint": np.full_like(time, setpoint),
        "output": output,
        "control": control,
        "error": error,
        "proportional": proportional,
        "integral": integral_term,
        "derivative": derivative_term,
    }

