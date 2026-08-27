"""M1 Quantity + supplier-level Reliability; no post-event procurement."""

import pyomo.environ as pyo

from robust_budget_allocation.data.mechanism_data import ReliabilityData


def _add_reliability_core(model, data, fixed_reliability=None):
    data.validate()
    base = data.base
    if fixed_reliability is not None:
        if set(fixed_reliability) != set(base.suppliers):
            raise ValueError("fixed Reliability must specify every supplier")
        if any(fixed_reliability[j] not in data.levels[j] for j in base.suppliers):
            raise ValueError("unknown fixed Reliability level")
    model.J = pyo.Set(initialize=base.suppliers, ordered=True)
    model.JK = pyo.Set(initialize=[(j, k) for j in base.suppliers for k in data.levels[j]], dimen=2, ordered=True)
    model.Omega = pyo.Set(initialize=base.scenarios, ordered=True)
    model.z = pyo.Var(model.JK, domain=pyo.Binary)
    model.q_level = pyo.Var(model.JK, domain=pyo.NonNegativeReals)
    model.one_level = pyo.Constraint(model.J, rule=lambda m, j: sum(m.z[j, k] for k in data.levels[j]) == 1)
    model.quantity_link = pyo.Constraint(model.JK, rule=lambda m, j, k: m.q_level[j, k] <= base.procurement_limit[j] * m.z[j, k])
    if fixed_reliability is not None:
        for j, k in model.JK:
            model.z[j, k].fix(int(k == fixed_reliability[j]))
    model._n3_fixed_reliability = dict(fixed_reliability) if fixed_reliability is not None else None
    model.theta = pyo.Var(domain=pyo.NonNegativeReals)
    model.x = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.u = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.h = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.C_Q = pyo.Expression(expr=sum(base.unit_cost[j] * model.q_level[j, k] for j, k in model.JK))
    model.C_R = pyo.Expression(expr=sum(data.fixed_premium[j][k] * model.z[j, k]
        + data.unit_premium[j][k] * model.q_level[j, k] for j, k in model.JK))
    model.delivered = pyo.Expression(model.Omega, rule=lambda m, w: sum(
        data.fulfillment[w][j][k] * m.q_level[j, k] for j, k in m.JK))
    model.demand_balance = pyo.Constraint(model.Omega, rule=lambda m, w: m.x[w] + m.u[w] == base.demand[w])


def build_m1(data: ReliabilityData, *, fixed_reliability=None):
    model = pyo.ConcreteModel(name="M1 Quantity + Reliability")
    _add_reliability_core(model, data, fixed_reliability)
    model.first_stage_cost = pyo.Expression(expr=model.C_Q + model.C_R)
    model.cash_budget = pyo.Constraint(expr=model.first_stage_cost <= data.base.budget)
    model.resource_balance = pyo.Constraint(model.Omega, rule=lambda m, w: m.x[w] + m.h[w] == m.delivered[w])
    model.worst_loss = pyo.Constraint(model.Omega, rule=lambda m, w: m.theta >= data.base.shortage_penalty * m.u[w])
    model.total_cost = pyo.Objective(expr=model.first_stage_cost + model.theta, sense=pyo.minimize)
    return model


def solve_m1(data: ReliabilityData, *, fixed_reliability=None, **kwargs):
    from .mechanism_support import solve_mechanism
    return solve_mechanism(data, build_m1(data, fixed_reliability=fixed_reliability),
                           model_kind="M1", restrictions={"fixed_reliability": fixed_reliability}, **kwargs)
