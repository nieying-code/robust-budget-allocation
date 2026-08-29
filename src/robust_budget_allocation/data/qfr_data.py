"""Immutable heterogeneous-material inputs for the Q-F-R v2 model family."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from numbers import Real
from types import MappingProxyType
from typing import Any

from robust_budget_allocation.io.hashing import canonical_json_sha256


RELIABILITY_LEVELS = (0, 1, 2)


def _ordered_ids(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError(f"{name} must be a nonempty ordered tuple/list")
    result = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{name} identifiers must be nonempty strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} identifiers must be unique")
    return result


def _exact_keys(values: object, expected: Sequence[object], name: str) -> Mapping[Any, Any]:
    if not isinstance(values, Mapping) or set(values) != set(expected):
        raise ValueError(f"{name} keys must exactly match their declared index")
    return values


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def _bounded(
    value: object,
    name: str,
    *,
    lower: float,
    upper: float | None = None,
    strict_lower: bool = False,
) -> float:
    number = _finite(value, name)
    if (number <= lower if strict_lower else number < lower) or (
        upper is not None and number > upper
    ):
        qualifier = ">" if strict_lower else ">="
        ceiling = f" and <= {upper}" if upper is not None else ""
        raise ValueError(f"{name} must be {qualifier} {lower}{ceiling}")
    return number


def _item_values(values: object, items: tuple[str, ...], name: str) -> dict[str, Any]:
    mapping = _exact_keys(values, items, name)
    return {item: mapping[item] for item in items}


def _level_values(values: object, items: tuple[str, ...], name: str) -> dict[str, dict[int, Any]]:
    outer = _exact_keys(values, items, name)
    result: dict[str, dict[int, Any]] = {}
    for item in items:
        raw = outer[item]
        if not isinstance(raw, Mapping):
            raise ValueError(f"{name}[{item}] must be a level mapping")
        if set(raw) == set(RELIABILITY_LEVELS) and all(type(key) is int for key in raw):
            result[item] = {level: raw[level] for level in RELIABILITY_LEVELS}
        elif set(raw) == {str(level) for level in RELIABILITY_LEVELS}:
            result[item] = {level: raw[str(level)] for level in RELIABILITY_LEVELS}
        else:
            raise ValueError(
                f"{name}[{item}] keys must be exactly reliability levels {RELIABILITY_LEVELS}"
            )
    return result


def _scenario_item_values(
    values: object,
    scenarios: tuple[str, ...],
    items: tuple[str, ...],
    name: str,
) -> dict[str, dict[str, Any]]:
    outer = _exact_keys(values, scenarios, name)
    return {
        scenario: _item_values(outer[scenario], items, f"{name}[{scenario}]")
        for scenario in scenarios
    }


def _freeze_item(values: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType(dict(values))


def _freeze_level(values: Mapping[str, Mapping[int, float]]) -> Mapping[str, Mapping[int, float]]:
    return MappingProxyType(
        {item: MappingProxyType(dict(levels)) for item, levels in values.items()}
    )


def _freeze_scenario(
    values: Mapping[str, Mapping[str, float]],
) -> Mapping[str, Mapping[str, float]]:
    return MappingProxyType(
        {scenario: MappingProxyType(dict(items)) for scenario, items in values.items()}
    )


@dataclass(frozen=True)
class QFRData:
    """Complete finite-scenario data for M0=Q, M1=Q+F, and M2=Q+F+R."""

    items: tuple[str, ...]
    scenarios: tuple[str, ...]
    budget: float
    tau: float
    q_unit_cost: Mapping[str, float]
    storage_cost: Mapping[str, float]
    retention: Mapping[str, float]
    flexible_capacity: Mapping[str, float]
    reservation_cost: Mapping[str, float]
    reliability_cost: Mapping[str, Mapping[int, float]]
    reliability_mitigation: Mapping[str, Mapping[int, float]]
    exercise_cost: Mapping[str, float]
    shortage_cost: Mapping[str, float]
    demand: Mapping[str, Mapping[str, float]]
    disruption: Mapping[str, Mapping[str, float]]

    def __post_init__(self) -> None:
        items = _ordered_ids(self.items, "items")
        scenarios = _ordered_ids(self.scenarios, "scenarios")

        budget = _bounded(self.budget, "budget", lower=0)
        tau = _bounded(self.tau, "tau", lower=0)

        raw_item = {
            name: _item_values(getattr(self, name), items, name)
            for name in (
                "q_unit_cost",
                "storage_cost",
                "retention",
                "flexible_capacity",
                "reservation_cost",
                "exercise_cost",
                "shortage_cost",
            )
        }
        raw_levels = {
            name: _level_values(getattr(self, name), items, name)
            for name in ("reliability_cost", "reliability_mitigation")
        }
        raw_scenarios = {
            name: _scenario_item_values(getattr(self, name), scenarios, items, name)
            for name in ("demand", "disruption")
        }

        item_values: dict[str, dict[str, float]] = {name: {} for name in raw_item}
        for item in items:
            item_values["q_unit_cost"][item] = _bounded(
                raw_item["q_unit_cost"][item], f"q_unit_cost[{item}]", lower=0, strict_lower=True
            )
            item_values["storage_cost"][item] = _bounded(
                raw_item["storage_cost"][item], f"storage_cost[{item}]", lower=0
            )
            item_values["retention"][item] = _bounded(
                raw_item["retention"][item], f"retention[{item}]", lower=0,
                upper=1, strict_lower=True
            )
            item_values["flexible_capacity"][item] = _bounded(
                raw_item["flexible_capacity"][item], f"flexible_capacity[{item}]", lower=0
            )
            for name in ("reservation_cost", "exercise_cost", "shortage_cost"):
                item_values[name][item] = _bounded(
                    raw_item[name][item], f"{name}[{item}]", lower=0, strict_lower=True
                )

        level_values: dict[str, dict[str, dict[int, float]]] = {
            name: {} for name in raw_levels
        }
        for item in items:
            reliability_cost = {
                level: _bounded(
                    raw_levels["reliability_cost"][item][level],
                    f"reliability_cost[{item}][{level}]",
                    lower=0,
                )
                for level in RELIABILITY_LEVELS
            }
            mitigation = {
                level: _bounded(
                    raw_levels["reliability_mitigation"][item][level],
                    f"reliability_mitigation[{item}][{level}]",
                    lower=0,
                    upper=1,
                )
                for level in RELIABILITY_LEVELS
            }
            if not (
                reliability_cost[0] == 0
                and 0 < reliability_cost[1] < reliability_cost[2]
            ):
                raise ValueError(
                    f"reliability_cost[{item}] must satisfy c_R[0]=0<c_R[1]<c_R[2]"
                )
            if not (mitigation[0] == 0 and 0 < mitigation[1] < mitigation[2] < 1):
                raise ValueError(
                    f"reliability_mitigation[{item}] must satisfy eta[0]=0<eta[1]<eta[2]<1"
                )
            level_values["reliability_cost"][item] = reliability_cost
            level_values["reliability_mitigation"][item] = mitigation

        scenario_values: dict[str, dict[str, dict[str, float]]] = {
            name: {} for name in raw_scenarios
        }
        for scenario in scenarios:
            scenario_values["demand"][scenario] = {
                item: _bounded(
                    raw_scenarios["demand"][scenario][item],
                    f"demand[{scenario}][{item}]",
                    lower=0,
                )
                for item in items
            }
            scenario_values["disruption"][scenario] = {
                item: _bounded(
                    raw_scenarios["disruption"][scenario][item],
                    f"disruption[{scenario}][{item}]",
                    lower=0,
                    upper=1,
                )
                for item in items
            }

        object.__setattr__(self, "items", items)
        object.__setattr__(self, "scenarios", scenarios)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "tau", tau)
        for name, values in item_values.items():
            object.__setattr__(self, name, _freeze_item(values))
        for name, values in level_values.items():
            object.__setattr__(self, name, _freeze_level(values))
        for name, values in scenario_values.items():
            object.__setattr__(self, name, _freeze_scenario(values))

    def validate(self) -> None:
        """Revalidate the immutable instance using the production schema contract."""

        type(self)(**{
            "items": self.items,
            "scenarios": self.scenarios,
            "budget": self.budget,
            "tau": self.tau,
            "q_unit_cost": self.q_unit_cost,
            "storage_cost": self.storage_cost,
            "retention": self.retention,
            "flexible_capacity": self.flexible_capacity,
            "reservation_cost": self.reservation_cost,
            "reliability_cost": self.reliability_cost,
            "reliability_mitigation": self.reliability_mitigation,
            "exercise_cost": self.exercise_cost,
            "shortage_cost": self.shortage_cost,
            "demand": self.demand,
            "disruption": self.disruption,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "model_family": "heterogeneous_material_qfr",
            "items": list(self.items),
            "scenarios": list(self.scenarios),
            "reliability_levels": list(RELIABILITY_LEVELS),
            "budget": self.budget,
            "tau": self.tau,
            **{
                name: dict(getattr(self, name))
                for name in (
                    "q_unit_cost",
                    "storage_cost",
                    "retention",
                    "flexible_capacity",
                    "reservation_cost",
                    "exercise_cost",
                    "shortage_cost",
                )
            },
            **{
                name: {
                    item: {str(level): getattr(self, name)[item][level] for level in RELIABILITY_LEVELS}
                    for item in self.items
                }
                for name in ("reliability_cost", "reliability_mitigation")
            },
            **{
                name: {
                    scenario: dict(getattr(self, name)[scenario])
                    for scenario in self.scenarios
                }
                for name in ("demand", "disruption")
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> QFRData:
        expected = {
            "schema_version",
            "model_family",
            "items",
            "scenarios",
            "reliability_levels",
            "budget",
            "tau",
            "q_unit_cost",
            "storage_cost",
            "retention",
            "flexible_capacity",
            "reservation_cost",
            "reliability_cost",
            "reliability_mitigation",
            "exercise_cost",
            "shortage_cost",
            "demand",
            "disruption",
        }
        _exact_keys(payload, tuple(expected), "Q-F-R data schema")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 2:
            raise ValueError("unsupported Q-F-R data schema_version")
        if payload["model_family"] != "heterogeneous_material_qfr":
            raise ValueError("model_family must identify the heterogeneous-material Q-F-R schema")
        if payload["reliability_levels"] != list(RELIABILITY_LEVELS):
            raise ValueError("reliability_levels must be exactly [0, 1, 2]")
        return cls(**{
            key: payload[key]
            for key in expected
            if key not in {"schema_version", "model_family", "reliability_levels"}
        })

    @property
    def data_sha256(self) -> str:
        return canonical_json_sha256(self.to_dict())

    @property
    def scenario_sha256(self) -> str:
        return canonical_json_sha256({
            "schema_version": 2,
            "model_family": "heterogeneous_material_qfr",
            "ordered_items": list(self.items),
            "ordered_scenarios": [
                {
                    "id": scenario,
                    "demand": dict(self.demand[scenario]),
                    "disruption": dict(self.disruption[scenario]),
                }
                for scenario in self.scenarios
            ],
        })
