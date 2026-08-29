"""M2=Q+F+R builder with F-specific reliability protection."""

from collections.abc import Iterable

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_common import build_qfr_model


def build_qfr_m2(
    data: QFRData,
    *,
    reliability_levels: Iterable[int] | None = None,
    disable_f: bool = False,
) -> pyo.ConcreteModel:
    """Build full M2 or its explicit r=0 nesting restriction."""

    return build_qfr_model(
        data,
        kind="M2",
        reliability_levels=reliability_levels,
        disable_f=disable_f,
    )
