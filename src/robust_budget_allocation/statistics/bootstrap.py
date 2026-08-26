"""Deterministic paired percentile bootstrap utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Callable, Iterable

import numpy as np


@dataclass(frozen=True)
class BootstrapResult:
    point_estimate: float
    confidence_interval: tuple[float, float]
    confidence_level: float
    resamples: int
    seed: int
    rng: str = "numpy.Generator(PCG64)"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def arithmetic_mean(values: np.ndarray) -> float:
    return float(np.mean(values))


def paired_bootstrap(
    left: Iterable[float],
    right: Iterable[float],
    *,
    seed: int,
    resamples: int = 10_000,
    confidence_level: float = 0.95,
    statistic: Callable[[np.ndarray], float] = arithmetic_mean,
) -> BootstrapResult:
    left_values = np.asarray(tuple(left), dtype=float)
    right_values = np.asarray(tuple(right), dtype=float)
    if left_values.ndim != 1 or right_values.ndim != 1:
        raise ValueError("paired bootstrap inputs must be one-dimensional")
    if len(left_values) == 0 or len(left_values) != len(right_values):
        raise ValueError("paired bootstrap requires equal nonempty samples")
    if not np.isfinite(left_values).all() or not np.isfinite(right_values).all():
        raise ValueError("paired bootstrap values must be finite")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be in (0, 1)")

    differences = left_values - right_values
    point = float(statistic(differences))
    if not math.isfinite(point):
        raise ValueError("statistic returned a non-finite point estimate")
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(0, len(differences), size=(resamples, len(differences)), endpoint=False)
    draws = np.asarray([statistic(differences[index]) for index in indices], dtype=float)
    if not np.isfinite(draws).all():
        raise ValueError("statistic returned non-finite bootstrap values")
    alpha = 1 - confidence_level
    lower, upper = np.percentile(
        draws,
        [100 * alpha / 2, 100 * (1 - alpha / 2)],
        method="linear",
    )
    return BootstrapResult(
        point_estimate=point,
        confidence_interval=(float(lower), float(upper)),
        confidence_level=confidence_level,
        resamples=resamples,
        seed=int(seed),
    )
