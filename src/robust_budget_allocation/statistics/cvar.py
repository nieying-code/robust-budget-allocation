"""Fractional upper-tail CVaR for empirical cost samples."""

from __future__ import annotations

import math
from typing import Iterable


def upper_tail_cvar(values: Iterable[float], *, tail_probability: float) -> float:
    samples = tuple(float(value) for value in values)
    if not samples:
        raise ValueError("CVaR requires at least one value")
    if not 0 < tail_probability <= 1:
        raise ValueError("tail_probability must be in (0, 1]")
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("CVaR values must be finite")
    ordered = sorted(samples, reverse=True)
    mass = tail_probability * len(ordered)
    complete = int(math.floor(mass))
    fraction = mass - complete
    total = sum(ordered[:complete])
    if fraction:
        total += fraction * ordered[complete]
    return total / mass
