"""First-stage state and exact accounting adapters for Q-F-R v2 R3."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.models.qfr_common import MODEL_KINDS
from .qfr_protocol import require_close, static_data_sha256, tolerance


@dataclass(frozen=True)
class QFRFirstStage:
    model_kind: str
    reliability_levels: tuple[int, ...]
    data_sha256: str
    scenario_sha256: str
    static_data_sha256: str
    q: dict[str, float]
    f: dict[str, dict[int, float]]
    z: dict[str, dict[int, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_kind": self.model_kind,
            "reliability_levels": list(self.reliability_levels),
            "data_sha256": self.data_sha256,
            "scenario_sha256": self.scenario_sha256,
            "static_data_sha256": self.static_data_sha256,
            "q": dict(self.q),
            "f": {
                item: {str(level): value for level, value in levels.items()}
                for item, levels in self.f.items()
            },
            "z": {
                item: {str(level): value for level, value in levels.items()}
                for item, levels in self.z.items()
            },
        }

    @property
    def sha256(self) -> str:
        return canonical_json_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> QFRFirstStage:
        required = {
            "model_kind",
            "reliability_levels",
            "data_sha256",
            "scenario_sha256",
            "static_data_sha256",
            "q",
            "f",
            "z",
        }
        if set(payload) != required:
            raise ValueError("first-stage fields are incomplete or unexpected")
        levels = tuple(payload["reliability_levels"])
        return cls(
            model_kind=str(payload["model_kind"]),
            reliability_levels=levels,
            data_sha256=str(payload["data_sha256"]),
            scenario_sha256=str(payload["scenario_sha256"]),
            static_data_sha256=str(payload["static_data_sha256"]),
            q={str(item): float(value) for item, value in payload["q"].items()},
            f={
                str(item): {int(level): float(value) for level, value in values.items()}
                for item, values in payload["f"].items()
            },
            z={
                str(item): {int(level): int(value) for level, value in values.items()}
                for item, values in payload["z"].items()
            },
        )


def levels_for_kind(kind: str) -> tuple[int, ...]:
    if kind == "M0":
        return ()
    if kind == "M1":
        return (0,)
    if kind == "M2":
        return (0, 1, 2)
    raise ValueError(f"unknown Q-F-R model kind: {kind!r}")


def _finite_value(component: Any, label: str) -> float:
    value = float(pyo.value(component))
    if not math.isfinite(value):
        raise ValueError(f"{label} must have a loaded finite value")
    return value


def extract_first_stage(
    full_data: QFRData,
    model: pyo.ConcreteModel,
) -> QFRFirstStage:
    """Extract a restricted/full solve while binding it to the complete R3 input."""

    full_data.validate()
    kind = getattr(model, "_qfr_kind", None)
    if kind not in MODEL_KINDS:
        raise ValueError("model is not a Q-F-R v2 model")
    levels = tuple(getattr(model, "_qfr_levels", ()))
    if levels != levels_for_kind(kind):
        raise ValueError("model reliability levels do not match its R3 model kind")
    if tuple(model.I) != full_data.items:
        raise ValueError("model item index does not match complete QFRData")
    q = {item: _finite_value(model.Q[item], f"Q[{item}]") for item in full_data.items}
    f: dict[str, dict[int, float]] = {item: {} for item in full_data.items}
    z: dict[str, dict[int, int]] = {item: {} for item in full_data.items}
    if kind != "M0":
        for item in full_data.items:
            for level in levels:
                f[item][level] = _finite_value(model.F[item, level], f"F[{item},{level}]")
                raw_z = _finite_value(model.z[item, level], f"z[{item},{level}]")
                if not (abs(raw_z) <= tolerance(raw_z, 0) or abs(raw_z - 1) <= tolerance(raw_z, 1)):
                    raise ValueError(f"z[{item},{level}] is not binary under R3 tolerance")
                z[item][level] = int(round(raw_z))
    result = QFRFirstStage(
        model_kind=kind,
        reliability_levels=levels,
        data_sha256=full_data.data_sha256,
        scenario_sha256=full_data.scenario_sha256,
        static_data_sha256=static_data_sha256(full_data),
        q=q,
        f=f,
        z=z,
    )
    validate_first_stage(full_data, result)
    return result


def validate_first_stage(data: QFRData, decision: QFRFirstStage) -> float:
    data.validate()
    if decision.model_kind not in MODEL_KINDS:
        raise ValueError("unknown first-stage model kind")
    if decision.reliability_levels != levels_for_kind(decision.model_kind):
        raise ValueError("first-stage reliability levels do not match model kind")
    if (
        decision.data_sha256 != data.data_sha256
        or decision.scenario_sha256 != data.scenario_sha256
        or decision.static_data_sha256 != static_data_sha256(data)
    ):
        raise ValueError("first-stage Q-F-R data identity mismatch")
    if set(decision.q) != set(data.items) or set(decision.f) != set(data.items) or set(
        decision.z
    ) != set(data.items):
        raise ValueError("first-stage item coverage mismatch")
    levels = decision.reliability_levels
    for item in data.items:
        q = float(decision.q[item])
        if not math.isfinite(q) or q < -tolerance(q, 0):
            raise ValueError(f"invalid Q[{item}]")
        if set(decision.f[item]) != set(levels) or set(decision.z[item]) != set(levels):
            raise ValueError(f"first-stage reliability coverage mismatch for {item}")
        selected = 0
        for level in levels:
            f = float(decision.f[item][level])
            z = decision.z[item][level]
            if not math.isfinite(f) or f < -tolerance(f, 0) or type(z) is not int or z not in (0, 1):
                raise ValueError(f"invalid F/z for {item},{level}")
            if f > data.flexible_capacity[item] * z + tolerance(
                f, data.flexible_capacity[item] * z
            ):
                raise ValueError(f"Fbar capacity link violated for {item},{level}")
            selected += z
        if selected > 1:
            raise ValueError(f"multiple reliability levels selected for {item}")
    pre = first_stage_cost(data, decision)
    if pre > data.budget + tolerance(pre, data.budget):
        raise ValueError("first-stage cash exceeds fixed total budget")
    return pre


def first_stage_cost(data: QFRData, decision: QFRFirstStage) -> float:
    q_cost = sum(
        (data.q_unit_cost[item] + data.storage_cost[item] * data.tau)
        * decision.q[item]
        for item in data.items
    )
    f_cost = sum(
        data.reservation_cost[item] * decision.f[item][level]
        for item in data.items
        for level in decision.reliability_levels
    )
    r_cost = sum(
        data.reliability_cost[item][level] * decision.f[item][level]
        for item in data.items
        for level in decision.reliability_levels
    )
    value = float(q_cost + f_cost + r_cost)
    if not math.isfinite(value):
        raise ValueError("first-stage cost must be finite")
    return value


def require_same_decision(left: QFRFirstStage, right: QFRFirstStage) -> None:
    """Strict identity helper for replay ownership, not an optimal-solution tie rule."""

    if left.model_kind != right.model_kind or left.reliability_levels != right.reliability_levels:
        raise ValueError("first-stage kinds differ")
    if left.data_sha256 != right.data_sha256 or left.scenario_sha256 != right.scenario_sha256:
        raise ValueError("first-stage identities differ")
    for item in left.q:
        require_close(left.q[item], right.q[item], f"Q[{item}]")
        for level in left.reliability_levels:
            require_close(left.f[item][level], right.f[item][level], f"F[{item},{level}]")
            if left.z[item][level] != right.z[item][level]:
                raise ValueError(f"z[{item},{level}] differs")
