"""Scale-aware feasibility checks for loaded Q-F-R solver solutions.

These rules validate numerical representations only. They do not relax model
constraints, change solver settings, or participate in A1 convergence decisions.
"""

from __future__ import annotations

import math


VALIDATION_ABSOLUTE_TOLERANCE = 1e-7
VALIDATION_RELATIVE_TOLERANCE = 1e-12
VALIDATION_RULE_ID = "QFR_SCALE_AWARE_FEASIBILITY_V1"


def reference_scale(*values: float) -> float:
    numeric = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in numeric):
        raise ValueError("Q-F-R numerical reference scale requires finite values")
    return max(1.0, *(abs(value) for value in numeric))


def feasibility_threshold(
    *scale_values: float,
    absolute_tolerance: float = VALIDATION_ABSOLUTE_TOLERANCE,
) -> float:
    if (
        isinstance(absolute_tolerance, bool)
        or not math.isfinite(float(absolute_tolerance))
        or float(absolute_tolerance) <= 0
    ):
        raise ValueError("absolute tolerance must be positive and finite")
    return float(absolute_tolerance) + VALIDATION_RELATIVE_TOLERANCE * reference_scale(
        *scale_values
    )


def row_scaling_divisor(*values: float) -> float:
    """Return a balanced positive divisor without creating near-zero coefficients."""

    return math.sqrt(reference_scale(*values))


def violation_is_acceptable(
    violation: float,
    *scale_values: float,
    absolute_tolerance: float = VALIDATION_ABSOLUTE_TOLERANCE,
) -> bool:
    numeric = float(violation)
    if not math.isfinite(numeric):
        return False
    return max(0.0, numeric) <= feasibility_threshold(
        *scale_values, absolute_tolerance=absolute_tolerance
    )
