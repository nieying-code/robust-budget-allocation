"""Holm family-wise error correction for generic p-value families."""

from __future__ import annotations

import math
from typing import Iterable


def holm_adjust(p_values: Iterable[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in p_values)
    if not values:
        return ()
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in values):
        raise ValueError("p-values must be finite and in [0, 1]")
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = (len(values) - rank) * values[index]
        running = max(running, candidate)
        adjusted[index] = min(1.0, running)
    return tuple(adjusted)


def holm_rejections(p_values: Iterable[float], *, alpha: float = 0.05) -> tuple[bool, ...]:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    return tuple(value <= alpha for value in holm_adjust(p_values))
