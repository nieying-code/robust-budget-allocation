"""M2 with one paid binary emergency-procurement option under one total budget."""

import pyomo.environ as pyo

from robust_budget_allocation.data.mechanism_data import OptionData
from .m1 import _add_reliability_core


def build_m2(data: OptionData, *, fixed_option=None, fixed_reliability=None):
    data.validate()
    if fixed_option is not None and (type(fixed_option) is not int or fixed_option not in (0, 1)):
        raise ValueError("fixed_option must be integer 0 or 1")
    model = pyo.ConcreteModel(name="M2 Quantity + Reliability + F-OPTION")
    _add_reliability_core(model, data.reliability, fixed_reliability)
    model.y_F = pyo.Var(domain=pyo.Binary)
    if fixed_option is not None:
        model.y_F.fix(fixed_option)
    model._n3_fixed_option = fixed_option
    model.g = pyo.Var(model.Omega, domain=pyo.NonNegativeReals)
    model.E = pyo.Expression(model.Omega, rule=lambda m, w: data.emergency_price[w] * m.g[w])
    model.option_fee = pyo.Expression(expr=data.option_fee * model.y_F)
    model.first_stage_cost = pyo.Expression(expr=model.C_Q + model.C_R + model.option_fee)
    model.cash_budget = pyo.Constraint(expr=model.first_stage_cost <= data.base.budget)
    model.option_cap = pyo.Constraint(model.Omega, rule=lambda m, w: m.E[w] <= data.option_cap * m.y_F)
    model.scenario_budget = pyo.Constraint(model.Omega, rule=lambda m, w: m.first_stage_cost + m.E[w] <= data.base.budget)
    model.resource_balance = pyo.Constraint(model.Omega, rule=lambda m, w: m.x[w] + m.h[w] == m.delivered[w] + m.g[w])
    model.worst_loss = pyo.Constraint(model.Omega, rule=lambda m, w: m.theta >= m.E[w] + data.base.shortage_penalty * m.u[w])
    model.total_cost = pyo.Objective(expr=model.first_stage_cost + model.theta, sense=pyo.minimize)
    return model


def solve_m2(data: OptionData, *, fixed_option=None, fixed_reliability=None, **kwargs):
    from .mechanism_support import solve_mechanism
    return solve_mechanism(data, build_m2(data, fixed_option=fixed_option, fixed_reliability=fixed_reliability),
        model_kind="M2", restrictions={"fixed_option": fixed_option, "fixed_reliability": fixed_reliability}, **kwargs)
