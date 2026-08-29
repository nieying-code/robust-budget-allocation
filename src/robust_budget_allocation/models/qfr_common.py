"""Shared linear construction for the heterogeneous-material Q-F-R v2 models."""

from __future__ import annotations

from collections.abc import Iterable

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS


MODEL_KINDS = ("M0", "M1", "M2")


def _levels_for(kind: str, reliability_levels: Iterable[int] | None) -> tuple[int, ...]:
    if kind not in MODEL_KINDS:
        raise ValueError(f"unknown Q-F-R model kind: {kind}")
    if kind == "M0":
        if reliability_levels is not None:
            raise ValueError("M0 has no flexible-capacity reliability levels")
        return ()
    if reliability_levels is None:
        return (0,) if kind == "M1" else RELIABILITY_LEVELS
    levels = tuple(reliability_levels)
    if not levels or len(set(levels)) != len(levels):
        raise ValueError("reliability level restriction must be nonempty and unique")
    if any(type(level) is not int or level not in RELIABILITY_LEVELS for level in levels):
        raise ValueError("reliability levels must be selected from (0, 1, 2)")
    if kind == "M1" and levels != (0,):
        raise ValueError("M1 permits only the base reliability level r=0")
    if kind == "M2" and levels not in ((0,), RELIABILITY_LEVELS):
        raise ValueError("M2 supports the full level set or the r=0 nesting restriction")
    return levels


def build_qfr_model(
    data: QFRData,
    *,
    kind: str,
    reliability_levels: Iterable[int] | None = None,
    disable_f: bool = False,
) -> pyo.ConcreteModel:
    """Build one finite-scenario v2 model without invoking an algorithm or solver."""

    if not isinstance(data, QFRData):
        raise ValueError("data must be QFRData")
    data.validate()
    levels = _levels_for(kind, reliability_levels)
    if kind == "M0" and disable_f:
        raise ValueError("M0 already excludes F")

    model = pyo.ConcreteModel(name=f"Q-F-R v2 {kind}")
    model._qfr_kind = kind
    model._qfr_levels = levels
    model._qfr_f_disabled = bool(disable_f)
    model.I = pyo.Set(initialize=data.items, ordered=True)
    model.Omega = pyo.Set(initialize=data.scenarios, ordered=True)
    model.Q = pyo.Var(model.I, domain=pyo.NonNegativeReals)
    model.theta = pyo.Var(domain=pyo.NonNegativeReals)
    model.u = pyo.Var(model.I, model.Omega, domain=pyo.NonNegativeReals)

    model.C_Q = pyo.Expression(expr=sum(
        (data.q_unit_cost[item] + data.storage_cost[item] * data.tau) * model.Q[item]
        for item in model.I
    ))
    model.effective_Q = pyo.Expression(
        model.I, rule=lambda m, item: data.retention[item] * m.Q[item]
    )

    if kind == "M0":
        model.C_F = pyo.Expression(expr=0.0)
        model.C_R = pyo.Expression(expr=0.0)
        model.C_pre = pyo.Expression(expr=model.C_Q)
        model.exercise_cost = pyo.Expression(model.Omega, rule=lambda _m, _scenario: 0.0)
        model.shortage_loss = pyo.Expression(
            model.Omega,
            rule=lambda m, scenario: sum(
                data.shortage_cost[item] * m.u[item, scenario] for item in m.I
            ),
        )
        model.scenario_loss = pyo.Expression(
            model.Omega, rule=lambda m, scenario: m.shortage_loss[scenario]
        )
        model.demand_balance = pyo.Constraint(
            model.I,
            model.Omega,
            rule=lambda m, item, scenario: (
                m.effective_Q[item] + m.u[item, scenario] >= data.demand[scenario][item]
            ),
        )
    else:
        model.R = pyo.Set(initialize=levels, ordered=True)
        model.F = pyo.Var(model.I, model.R, domain=pyo.NonNegativeReals)
        model.z = pyo.Var(model.I, model.R, domain=pyo.Binary)
        model.x = pyo.Var(model.I, model.Omega, domain=pyo.NonNegativeReals)
        model.one_reliability_level = pyo.Constraint(
            model.I,
            rule=lambda m, item: sum(m.z[item, level] for level in m.R) <= 1,
        )
        model.capacity_link = pyo.Constraint(
            model.I,
            model.R,
            rule=lambda m, item, level: (
                m.F[item, level] <= data.flexible_capacity[item] * m.z[item, level]
            ),
        )
        if disable_f:
            for item in data.items:
                for level in levels:
                    model.F[item, level].fix(0.0)
                    model.z[item, level].fix(0)

        model.total_F = pyo.Expression(
            model.I, rule=lambda m, item: sum(m.F[item, level] for level in m.R)
        )
        model.C_F = pyo.Expression(expr=sum(
            data.reservation_cost[item] * model.F[item, level]
            for item in model.I for level in model.R
        ))
        model.C_R = pyo.Expression(expr=sum(
            data.reliability_cost[item][level] * model.F[item, level]
            for item in model.I for level in model.R
        ))
        model.C_pre = pyo.Expression(expr=model.C_Q + model.C_F + model.C_R)
        model.rho = pyo.Expression(
            model.I,
            model.Omega,
            model.R,
            rule=lambda _m, item, scenario, level: (
                1
                - (1 - data.reliability_mitigation[item][level])
                * data.disruption[scenario][item]
            ),
        )
        model.fulfillable_F = pyo.Expression(
            model.I,
            model.Omega,
            rule=lambda m, item, scenario: sum(
                m.rho[item, scenario, level] * m.F[item, level] for level in m.R
            ),
        )
        model.exercise_limit = pyo.Constraint(
            model.I,
            model.Omega,
            rule=lambda m, item, scenario: (
                m.x[item, scenario] <= m.fulfillable_F[item, scenario]
            ),
        )
        model.exercise_cost = pyo.Expression(
            model.Omega,
            rule=lambda m, scenario: sum(
                data.exercise_cost[item] * m.x[item, scenario] for item in m.I
            ),
        )
        model.shortage_loss = pyo.Expression(
            model.Omega,
            rule=lambda m, scenario: sum(
                data.shortage_cost[item] * m.u[item, scenario] for item in m.I
            ),
        )
        model.scenario_loss = pyo.Expression(
            model.Omega,
            rule=lambda m, scenario: m.exercise_cost[scenario] + m.shortage_loss[scenario],
        )
        model.demand_balance = pyo.Constraint(
            model.I,
            model.Omega,
            rule=lambda m, item, scenario: (
                m.effective_Q[item] + m.x[item, scenario] + m.u[item, scenario]
                >= data.demand[scenario][item]
            ),
        )

    model.scenario_budget = pyo.Constraint(
        model.Omega,
        rule=lambda m, scenario: m.C_pre + m.exercise_cost[scenario] <= data.budget,
    )
    model.unused_cash = pyo.Expression(
        model.Omega,
        rule=lambda m, scenario: data.budget - m.C_pre - m.exercise_cost[scenario],
    )
    model.worst_loss = pyo.Constraint(
        model.Omega,
        rule=lambda m, scenario: m.theta >= m.scenario_loss[scenario],
    )
    model.total_cost = pyo.Objective(expr=model.C_pre + model.theta, sense=pyo.minimize)
    return model
