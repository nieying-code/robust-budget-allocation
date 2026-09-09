"""Numerical feasibility rules shared by final Q-F-R exact paths.

The relative term is applied to a constraint-family-specific physical scale.
Nonnegativity and integrality remain governed by their existing absolute checks.
"""

from __future__ import annotations

import math
from typing import Final


VALIDATION_ABSOLUTE_TOLERANCE: Final = 1e-7
VALIDATION_RELATIVE_TOLERANCE: Final = 1e-12
VALIDATION_RULE_ID: Final = "QFR_FAMILY_SCALE_FEASIBILITY_V1"
VALIDATION_FAMILIES: Final = frozenset(
    {"objective_epigraph", "budget", "quantity_flow", "fulfillment_capacity"}
)


def family_reference_scale(family: str, *values: float) -> float:
    """Return the physical reference scale for one named constraint family."""

    if family not in VALIDATION_FAMILIES:
        raise ValueError(f"unknown Q-F-R numerical validation family: {family!r}")
    numeric = tuple(float(value) for value in values)
    if not numeric or any(not math.isfinite(value) for value in numeric):
        raise ValueError("family reference scale requires finite values")
    return max(1.0, *(abs(value) for value in numeric))


def family_feasibility_threshold(
    family: str,
    *scale_values: float,
    absolute_tolerance: float = VALIDATION_ABSOLUTE_TOLERANCE,
) -> float:
    """Return ``abs_tol + rel_tol * family_reference_scale``."""

    numeric_tolerance = float(absolute_tolerance)
    if (
        isinstance(absolute_tolerance, bool)
        or not math.isfinite(numeric_tolerance)
        or numeric_tolerance <= 0
    ):
        raise ValueError("absolute tolerance must be positive and finite")
    return numeric_tolerance + VALIDATION_RELATIVE_TOLERANCE * family_reference_scale(
        family, *scale_values
    )


def family_violation_is_acceptable(
    family: str,
    violation: float,
    *scale_values: float,
    absolute_tolerance: float = VALIDATION_ABSOLUTE_TOLERANCE,
) -> bool:
    numeric = float(violation)
    if not math.isfinite(numeric):
        return False
    return max(0.0, numeric) <= family_feasibility_threshold(
        family, *scale_values, absolute_tolerance=absolute_tolerance
    )


def row_scaling_divisor(family: str, *values: float) -> float:
    """Return a stable divisor for an algebraically equivalent scaled row."""

    return math.sqrt(family_reference_scale(family, *values))
