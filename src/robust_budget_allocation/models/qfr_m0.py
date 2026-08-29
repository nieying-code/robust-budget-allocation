"""M0=Q builder for the heterogeneous-material Q-F-R v2 family."""

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_common import build_qfr_model


def build_qfr_m0(data: QFRData) -> pyo.ConcreteModel:
    return build_qfr_model(data, kind="M0")
