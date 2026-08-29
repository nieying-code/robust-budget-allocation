"""Independent accounting and loaded-solution validation for Q-F-R v2 models."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_common import MODEL_KINDS


# Implementation-level feasibility check only; this is not an R3 correctness protocol.
R2_VALIDATION_TOLERANCE = 1e-7


@dataclass(frozen=True)
class QFRAccounting:
    model_kind: str
    reliability_levels: tuple[int, ...]
    objective: float
    theta: float
    C_Q: float
    C_F: float
    C_R: float
    C_pre: float
    q: dict[str, float]
    f: dict[str, dict[int, float]]
    z: dict[str, dict[int, int]]
    x: dict[str, dict[str, float]]
    u: dict[str, dict[str, float]]
    effective_q: dict[str, float]
    fulfillable_f: dict[str, dict[str, float]]
    exercise_cost: dict[str, float]
    shortage_loss: dict[str, float]
    scenario_loss: dict[str, float]
    unused_cash: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_kind": self.model_kind,
            "reliability_levels": list(self.reliability_levels),
            "objective": self.objective,
            "theta": self.theta,
            "C_Q": self.C_Q,
            "C_F": self.C_F,
            "C_R": self.C_R,
            "C_pre": self.C_pre,
            "q": dict(self.q),
            "f": {
                item: {str(level): value for level, value in levels.items()}
                for item, levels in self.f.items()
            },
            "z": {
                item: {str(level): value for level, value in levels.items()}
                for item, levels in self.z.items()
            },
            "x": {item: dict(values) for item, values in self.x.items()},
            "u": {item: dict(values) for item, values in self.u.items()},
            "effective_q": dict(self.effective_q),
            "fulfillable_f": {
                item: dict(values) for item, values in self.fulfillable_f.items()
            },
            "exercise_cost": dict(self.exercise_cost),
            "shortage_loss": dict(self.shortage_loss),
            "scenario_loss": dict(self.scenario_loss),
            "unused_cash": dict(self.unused_cash),
        }


def _value(component: Any, name: str) -> float:
    try:
        value = float(pyo.value(component))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} has no loaded finite value") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def validate_qfr_solution(
    data: QFRData,
    model: pyo.ConcreteModel,
    *,
    tolerance: float = R2_VALIDATION_TOLERANCE,
) -> QFRAccounting:
    """Recompute all scientific accounting and reject an invalid loaded solution."""

    if isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be a positive finite number")
    data.validate()
    kind = getattr(model, "_qfr_kind", None)
    if kind not in MODEL_KINDS:
        raise ValueError("model is not a Q-F-R v2 M0/M1/M2 model")
    levels = tuple(getattr(model, "_qfr_levels", ()))
    if tuple(model.I) != data.items or tuple(model.Omega) != data.scenarios:
        raise ValueError("model item/scenario indices do not match QFRData")

    def lower(value: float, bound: float, label: str) -> None:
        if value < bound - tolerance:
            raise ValueError(f"Q-F-R invariant failed: {label}")

    def upper(value: float, bound: float, label: str) -> None:
        if value > bound + tolerance:
            raise ValueError(f"Q-F-R invariant failed: {label}")

    def equal(value: float, expected: float, label: str) -> None:
        if not math.isclose(value, expected, abs_tol=tolerance, rel_tol=1e-9):
            raise ValueError(f"Q-F-R invariant failed: {label}")

    q = {item: _value(model.Q[item], f"Q[{item}]") for item in data.items}
    u = {
        item: {
            scenario: _value(model.u[item, scenario], f"u[{item},{scenario}]")
            for scenario in data.scenarios
        }
        for item in data.items
    }
    theta = _value(model.theta, "theta")
    lower(theta, 0, "theta nonnegative")
    for item in data.items:
        lower(q[item], 0, f"Q[{item}] nonnegative")
        for scenario in data.scenarios:
            lower(u[item][scenario], 0, f"u[{item},{scenario}] nonnegative")

    f: dict[str, dict[int, float]] = {item: {} for item in data.items}
    z: dict[str, dict[int, int]] = {item: {} for item in data.items}
    x: dict[str, dict[str, float]] = {
        item: {scenario: 0.0 for scenario in data.scenarios} for item in data.items
    }
    fulfillable_f: dict[str, dict[str, float]] = {
        item: {scenario: 0.0 for scenario in data.scenarios} for item in data.items
    }
    if kind != "M0":
        if tuple(model.R) != levels:
            raise ValueError("model reliability index does not match its declared restriction")
        for item in data.items:
            selected = 0
            for level in levels:
                f_value = _value(model.F[item, level], f"F[{item},{level}]")
                z_value = _value(model.z[item, level], f"z[{item},{level}]")
                lower(f_value, 0, f"F[{item},{level}] nonnegative")
                if not (math.isclose(z_value, 0, abs_tol=tolerance) or math.isclose(
                    z_value, 1, abs_tol=tolerance
                )):
                    raise ValueError(f"Q-F-R invariant failed: z[{item},{level}] binary")
                z_integer = int(round(z_value))
                upper(
                    f_value,
                    data.flexible_capacity[item] * z_integer,
                    f"Fbar capacity link for {item},{level}",
                )
                if getattr(model, "_qfr_f_disabled", False):
                    equal(f_value, 0, f"disabled F[{item},{level}]")
                    equal(z_integer, 0, f"disabled z[{item},{level}]")
                f[item][level] = f_value
                z[item][level] = z_integer
                selected += z_integer
            upper(selected, 1, f"one reliability level for {item}")
            for scenario in data.scenarios:
                x_value = _value(model.x[item, scenario], f"x[{item},{scenario}]")
                lower(x_value, 0, f"x[{item},{scenario}] nonnegative")
                fulfillment = sum(
                    (
                        1
                        - (1 - data.reliability_mitigation[item][level])
                        * data.disruption[scenario][item]
                    )
                    * f[item][level]
                    for level in levels
                )
                upper(x_value, fulfillment, f"flexible fulfillment for {item},{scenario}")
                x[item][scenario] = x_value
                fulfillable_f[item][scenario] = fulfillment

    effective_q = {
        item: data.retention[item] * q[item] for item in data.items
    }
    for item in data.items:
        for scenario in data.scenarios:
            lower(
                effective_q[item] + x[item][scenario] + u[item][scenario],
                data.demand[scenario][item],
                f"demand coverage for {item},{scenario}",
            )

    C_Q = sum(
        (data.q_unit_cost[item] + data.storage_cost[item] * data.tau) * q[item]
        for item in data.items
    )
    C_F = sum(
        data.reservation_cost[item] * f[item][level]
        for item in data.items for level in levels
    )
    C_R = sum(
        data.reliability_cost[item][level] * f[item][level]
        for item in data.items for level in levels
    )
    C_pre = C_Q + C_F + C_R
    exercise_cost = {
        scenario: sum(
            data.exercise_cost[item] * x[item][scenario] for item in data.items
        )
        for scenario in data.scenarios
    }
    shortage_loss = {
        scenario: sum(
            data.shortage_cost[item] * u[item][scenario] for item in data.items
        )
        for scenario in data.scenarios
    }
    scenario_loss = {
        scenario: exercise_cost[scenario] + shortage_loss[scenario]
        for scenario in data.scenarios
    }
    unused_cash = {
        scenario: data.budget - C_pre - exercise_cost[scenario]
        for scenario in data.scenarios
    }
    for scenario in data.scenarios:
        lower(unused_cash[scenario], 0, f"fixed total budget for {scenario}")
        lower(theta, scenario_loss[scenario], f"worst-loss epigraph for {scenario}")

    objective = C_pre + theta
    equal(_value(model.C_Q, "model.C_Q"), C_Q, "C_Q accounting")
    equal(_value(model.C_F, "model.C_F"), C_F, "C_F accounting")
    equal(_value(model.C_R, "model.C_R"), C_R, "C_R accounting")
    equal(_value(model.C_pre, "model.C_pre"), C_pre, "pre-disaster accounting")
    equal(_value(model.total_cost, "model.total_cost"), objective, "objective accounting")
    for scenario in data.scenarios:
        equal(
            _value(model.exercise_cost[scenario], f"model.exercise_cost[{scenario}]"),
            exercise_cost[scenario],
            f"exercise accounting for {scenario}",
        )
        equal(
            _value(model.shortage_loss[scenario], f"model.shortage_loss[{scenario}]"),
            shortage_loss[scenario],
            f"shortage accounting for {scenario}",
        )
        equal(
            _value(model.unused_cash[scenario], f"model.unused_cash[{scenario}]"),
            unused_cash[scenario],
            f"unused cash for {scenario}",
        )

    return QFRAccounting(
        model_kind=kind,
        reliability_levels=levels,
        objective=objective,
        theta=theta,
        C_Q=C_Q,
        C_F=C_F,
        C_R=C_R,
        C_pre=C_pre,
        q=q,
        f=f,
        z=z,
        x=x,
        u=u,
        effective_q=effective_q,
        fulfillable_f=fulfillable_f,
        exercise_cost=exercise_cost,
        shortage_loss=shortage_loss,
        scenario_loss=scenario_loss,
        unused_cash=unused_cash,
    )
