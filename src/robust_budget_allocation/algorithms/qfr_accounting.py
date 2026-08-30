"""Independent fail-closed replay of serialized Q-F-R solution accounting."""

from __future__ import annotations

import math
from typing import Any, Mapping

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_protocol import require_close, static_data_sha256, tolerance
from .qfr_state import QFRFirstStage, first_stage_cost, validate_first_stage


ACCOUNTING_FIELDS = {
    "model_kind",
    "reliability_levels",
    "data_sha256",
    "scenario_sha256",
    "objective",
    "theta",
    "C_Q",
    "C_F",
    "C_R",
    "C_pre",
    "q",
    "f",
    "z",
    "x",
    "u",
    "effective_q",
    "fulfillable_f",
    "exercise_cost",
    "shortage_loss",
    "scenario_loss",
    "unused_cash",
}


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _same_keys(value: Any, expected: set[Any], label: str) -> Mapping[Any, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{label} coverage mismatch")
    return value


def _nonnegative(value: float, label: str) -> None:
    if value < -tolerance(value, 0.0):
        raise ValueError(f"{label} is negative")


def validate_accounting_payload(
    full_data: QFRData,
    accounting_data: QFRData,
    decision: QFRFirstStage,
    payload: Mapping[str, Any],
    *,
    expected_objective: float,
    expected_theta: float,
) -> None:
    """Recompute every serialized accounting field and all model constraints."""

    full_data.validate()
    accounting_data.validate()
    validate_first_stage(full_data, decision)
    if static_data_sha256(accounting_data) != static_data_sha256(full_data):
        raise ValueError("accounting data changed static Q-F-R science")
    if set(payload) != ACCOUNTING_FIELDS:
        raise ValueError("Q-F-R accounting fields are incomplete or unexpected")
    levels = decision.reliability_levels
    if (
        payload["model_kind"] != decision.model_kind
        or payload["reliability_levels"] != list(levels)
        or payload["data_sha256"] != accounting_data.data_sha256
        or payload["scenario_sha256"] != accounting_data.scenario_sha256
    ):
        raise ValueError("Q-F-R accounting identity mismatch")

    items = set(accounting_data.items)
    scenarios = set(accounting_data.scenarios)
    level_keys = {str(level) for level in levels}
    q_raw = _same_keys(payload["q"], items, "accounting Q")
    f_raw = _same_keys(payload["f"], items, "accounting F")
    z_raw = _same_keys(payload["z"], items, "accounting z")
    x_raw = _same_keys(payload["x"], items, "accounting x")
    u_raw = _same_keys(payload["u"], items, "accounting u")
    effective_raw = _same_keys(payload["effective_q"], items, "effective Q")
    fulfillable_raw = _same_keys(payload["fulfillable_f"], items, "fulfillable F")

    q: dict[str, float] = {}
    f: dict[str, dict[int, float]] = {}
    z: dict[str, dict[int, int]] = {}
    x: dict[str, dict[str, float]] = {}
    u: dict[str, dict[str, float]] = {}
    for item in accounting_data.items:
        q[item] = _finite(q_raw[item], f"Q[{item}]")
        _nonnegative(q[item], f"Q[{item}]")
        require_close(q[item], decision.q[item], f"accounting Q[{item}]")
        item_f = _same_keys(f_raw[item], level_keys, f"accounting F[{item}]")
        item_z = _same_keys(z_raw[item], level_keys, f"accounting z[{item}]")
        f[item], z[item] = {}, {}
        selected = 0
        for level in levels:
            key = str(level)
            f_value = _finite(item_f[key], f"F[{item},{level}]")
            raw_z = item_z[key]
            if type(raw_z) is not int or raw_z not in (0, 1):
                raise ValueError(f"z[{item},{level}] is not binary")
            _nonnegative(f_value, f"F[{item},{level}]")
            require_close(f_value, decision.f[item][level], f"accounting F[{item},{level}]")
            if raw_z != decision.z[item][level]:
                raise ValueError(f"accounting z[{item},{level}] differs from first stage")
            if f_value > accounting_data.flexible_capacity[item] * raw_z + tolerance(
                f_value, accounting_data.flexible_capacity[item] * raw_z
            ):
                raise ValueError(f"Fbar link violated for {item},{level}")
            f[item][level], z[item][level] = f_value, raw_z
            selected += raw_z
        if selected > 1:
            raise ValueError(f"multiple reliability levels selected for {item}")
        item_x = _same_keys(x_raw[item], scenarios, f"accounting x[{item}]")
        item_u = _same_keys(u_raw[item], scenarios, f"accounting u[{item}]")
        item_fulfillable = _same_keys(
            fulfillable_raw[item], scenarios, f"fulfillable F[{item}]"
        )
        x[item], u[item] = {}, {}
        retained = accounting_data.retention[item] * q[item]
        if accounting_data.schema_version == 2:
            require_close(
                _finite(effective_raw[item], f"effective Q[{item}]"),
                retained,
                f"effective Q[{item}]",
            )
            available_raw = None
        else:
            available_raw = _same_keys(
                effective_raw[item], scenarios, f"effective Q[{item}]"
            )
        for scenario in accounting_data.scenarios:
            x_value = _finite(item_x[scenario], f"x[{item},{scenario}]")
            u_value = _finite(item_u[scenario], f"u[{item},{scenario}]")
            _nonnegative(x_value, f"x[{item},{scenario}]")
            _nonnegative(u_value, f"u[{item},{scenario}]")
            fulfillment = sum(
                (
                    1
                    - (1 - accounting_data.reliability_mitigation[item][level])
                    * accounting_data.disruption[scenario][item]
                )
                * f[item][level]
                for level in levels
            )
            require_close(
                _finite(item_fulfillable[scenario], f"fulfillable F[{item},{scenario}]"),
                fulfillment,
                f"fulfillable F[{item},{scenario}]",
            )
            if x_value > fulfillment + tolerance(x_value, fulfillment):
                raise ValueError(f"flexible fulfillment violated for {item},{scenario}")
            available = retained * accounting_data.q_availability[scenario][item]
            if available_raw is not None:
                require_close(
                    _finite(
                        available_raw[scenario],
                        f"effective Q[{item},{scenario}]",
                    ),
                    available,
                    f"effective Q[{item},{scenario}]",
                )
            if available + x_value + u_value < accounting_data.demand[scenario][item] - tolerance(
                available + x_value + u_value, accounting_data.demand[scenario][item]
            ):
                raise ValueError(f"demand coverage violated for {item},{scenario}")
            x[item][scenario], u[item][scenario] = x_value, u_value

    C_Q = sum(
        (accounting_data.q_unit_cost[item] + accounting_data.storage_cost[item] * accounting_data.tau)
        * q[item]
        for item in accounting_data.items
    )
    C_F = sum(
        accounting_data.reservation_cost[item] * f[item][level]
        for item in accounting_data.items
        for level in levels
    )
    C_R = sum(
        accounting_data.reliability_cost[item][level] * f[item][level]
        for item in accounting_data.items
        for level in levels
    )
    C_pre = C_Q + C_F + C_R
    require_close(C_pre, first_stage_cost(full_data, decision), "accounting first-stage cost")
    for key, value in {"C_Q": C_Q, "C_F": C_F, "C_R": C_R, "C_pre": C_pre}.items():
        require_close(_finite(payload[key], key), value, f"accounting {key}")

    exercise_raw = _same_keys(payload["exercise_cost"], scenarios, "exercise cost")
    shortage_raw = _same_keys(payload["shortage_loss"], scenarios, "shortage loss")
    loss_raw = _same_keys(payload["scenario_loss"], scenarios, "scenario loss")
    cash_raw = _same_keys(payload["unused_cash"], scenarios, "unused cash")
    theta = _finite(payload["theta"], "theta")
    _nonnegative(theta, "theta")
    require_close(theta, expected_theta, "accounting theta")
    for scenario in accounting_data.scenarios:
        exercise = sum(
            accounting_data.exercise_cost[item] * x[item][scenario]
            for item in accounting_data.items
        )
        shortage = sum(
            accounting_data.shortage_cost[item] * u[item][scenario]
            for item in accounting_data.items
        )
        loss = exercise + shortage
        unused = accounting_data.budget - C_pre - exercise
        require_close(_finite(exercise_raw[scenario], f"exercise cost[{scenario}]"), exercise, f"exercise cost[{scenario}]")
        require_close(_finite(shortage_raw[scenario], f"shortage loss[{scenario}]"), shortage, f"shortage loss[{scenario}]")
        require_close(_finite(loss_raw[scenario], f"scenario loss[{scenario}]"), loss, f"scenario loss[{scenario}]")
        require_close(_finite(cash_raw[scenario], f"unused cash[{scenario}]"), unused, f"unused cash[{scenario}]")
        if unused < -tolerance(unused, 0.0):
            raise ValueError(f"fixed total budget violated for {scenario}")
        if theta < loss - tolerance(theta, loss):
            raise ValueError(f"theta epigraph violated for {scenario}")
    objective = C_pre + theta
    require_close(_finite(payload["objective"], "accounting objective"), objective, "accounting objective")
    require_close(objective, expected_objective, "accounting/solver objective")
