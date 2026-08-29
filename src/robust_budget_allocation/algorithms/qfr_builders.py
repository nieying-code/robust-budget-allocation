"""Reviewed R2 builder adapters used by R3 without changing model semantics."""

from __future__ import annotations

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.models.qfr_m0 import build_qfr_m0
from robust_budget_allocation.models.qfr_m1 import build_qfr_m1
from robust_budget_allocation.models.qfr_m2 import build_qfr_m2


def build_qfr_extensive_form(data: QFRData, model_kind: str) -> pyo.ConcreteModel:
    """Build the complete finite-scenario R2 model as the R3 EF benchmark."""

    if model_kind == "M0":
        return build_qfr_m0(data)
    if model_kind == "M1":
        return build_qfr_m1(data)
    if model_kind == "M2":
        return build_qfr_m2(data)
    raise ValueError(f"unknown Q-F-R model kind: {model_kind!r}")


def build_qfr_restricted_master(data: QFRData, model_kind: str) -> pyo.ConcreteModel:
    """The restricted master is exactly the reviewed R2 model on a scenario subset."""

    return build_qfr_extensive_form(data, model_kind)
