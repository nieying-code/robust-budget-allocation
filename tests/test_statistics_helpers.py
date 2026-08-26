import math

import pytest

from robust_budget_allocation.statistics.bootstrap import paired_bootstrap
from robust_budget_allocation.statistics.cvar import upper_tail_cvar
from robust_budget_allocation.statistics.multiple_testing import holm_adjust, holm_rejections


def test_fractional_empirical_cvar_known_samples() -> None:
    assert upper_tail_cvar([1, 2, 3, 4], tail_probability=0.5) == 3.5
    assert upper_tail_cvar([1, 2, 3, 4], tail_probability=0.375) == pytest.approx(11 / 3)
    assert upper_tail_cvar([1, 2, 3, 4], tail_probability=1.0) == 2.5


def test_cvar_edge_cases() -> None:
    with pytest.raises(ValueError):
        upper_tail_cvar([], tail_probability=0.5)
    with pytest.raises(ValueError):
        upper_tail_cvar([1], tail_probability=0)
    with pytest.raises(ValueError):
        upper_tail_cvar([math.inf], tail_probability=0.5)


def test_paired_bootstrap_is_deterministic_with_fixed_rng() -> None:
    first = paired_bootstrap([3, 4, 9], [1, 2, 3], seed=1729, resamples=500)
    second = paired_bootstrap([3, 4, 9], [1, 2, 3], seed=1729, resamples=500)
    assert first == second
    assert first.point_estimate == pytest.approx(10 / 3)
    assert first.rng == "numpy.Generator(PCG64)"


def test_paired_bootstrap_constant_and_edge_cases() -> None:
    result = paired_bootstrap([2, 2], [1, 1], seed=1, resamples=20)
    assert result.confidence_interval == (1.0, 1.0)
    with pytest.raises(ValueError, match="equal nonempty"):
        paired_bootstrap([1], [], seed=1)
    with pytest.raises(ValueError, match="finite"):
        paired_bootstrap([1], [math.nan], seed=1)
    with pytest.raises(ValueError, match="positive"):
        paired_bootstrap([1], [1], seed=1, resamples=0)


def test_holm_adjustment_and_rejections() -> None:
    adjusted = holm_adjust([0.01, 0.04, 0.03])
    assert adjusted == pytest.approx((0.03, 0.06, 0.06))
    assert holm_rejections([0.01, 0.04, 0.03]) == (True, False, False)
    assert holm_adjust([]) == ()
    with pytest.raises(ValueError):
        holm_adjust([-0.1])
