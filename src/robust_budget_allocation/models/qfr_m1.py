"""M1=Q+F builder, restricted to base reliability level r=0."""

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_common import build_qfr_model


def build_qfr_m1(data: QFRData, *, disable_f: bool = False) -> pyo.ConcreteModel:
    """Build M1; ``disable_f`` is the explicit M1|F=0 nesting restriction."""

    return build_qfr_model(data, kind="M1", reliability_levels=(0,), disable_f=disable_f)
