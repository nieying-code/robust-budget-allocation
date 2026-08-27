"""Immutable, single-resource M0 inputs with explicit scenario ordering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from numbers import Real
from types import MappingProxyType
from typing import Any

from robust_budget_allocation.io.hashing import canonical_json_sha256


def _number(value: object, name: str, *, upper: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    if not math.isfinite(value) or value < 0 or (upper is not None and value > upper):
        raise ValueError(f"{name} is nonfinite or outside its permitted range")


def _ids(values: object, name: str) -> None:
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError(f"{name} must be a nonempty ordered tuple/list")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} identifiers must be nonempty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} identifiers must be unique")


def _keys(values: object, expected: object, name: str) -> None:
    if not isinstance(values, Mapping) or set(values) != set(expected):
        raise ValueError(f"{name} keys must exactly match their declared index")


@dataclass(frozen=True)
class BudgetAllocationData:
    """One resource; fulfillment is exogenous and always at the base level."""

    suppliers: tuple[str, ...]
    scenarios: tuple[str, ...]
    budget: float
    unit_cost: Mapping[str, float]
    procurement_limit: Mapping[str, float]
    demand: Mapping[str, float]
    base_fulfillment: Mapping[str, Mapping[str, float]]
    shortage_penalty: float
    resource_id: str = "resource"

    def __post_init__(self) -> None:
        self.validate()
        object.__setattr__(self, "suppliers", tuple(self.suppliers))
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
        object.__setattr__(self, "budget", float(self.budget))
        object.__setattr__(self, "shortage_penalty", float(self.shortage_penalty))
        for name in ("unit_cost", "procurement_limit", "demand"):
            values = getattr(self, name)
            object.__setattr__(self, name, MappingProxyType({k: float(v) for k, v in values.items()}))
        object.__setattr__(self, "base_fulfillment", MappingProxyType({
            w: MappingProxyType({j: float(self.base_fulfillment[w][j]) for j in self.suppliers})
            for w in self.scenarios
        }))

    def validate(self) -> None:
        _ids(self.suppliers, "suppliers")
        _ids(self.scenarios, "scenarios")
        if not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError("resource_id must identify exactly one resource")
        _number(self.budget, "budget")
        _number(self.shortage_penalty, "shortage_penalty")
        for name in ("unit_cost", "procurement_limit"):
            values = getattr(self, name)
            _keys(values, self.suppliers, name)
            for j in self.suppliers:
                _number(values[j], f"{name}[{j}]")
        _keys(self.demand, self.scenarios, "demand")
        _keys(self.base_fulfillment, self.scenarios, "base_fulfillment")
        for w in self.scenarios:
            _number(self.demand[w], f"demand[{w}]")
            _keys(self.base_fulfillment[w], self.suppliers, f"base_fulfillment[{w}]")
            for j in self.suppliers:
                _number(self.base_fulfillment[w][j], f"base_fulfillment[{w}][{j}]", upper=1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "resource_id": self.resource_id,
            "suppliers": list(self.suppliers),
            "scenarios": list(self.scenarios),
            "budget": self.budget,
            "unit_cost": dict(self.unit_cost),
            "procurement_limit": dict(self.procurement_limit),
            "demand": dict(self.demand),
            "base_fulfillment": {w: dict(self.base_fulfillment[w]) for w in self.scenarios},
            "shortage_penalty": self.shortage_penalty,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> BudgetAllocationData:
        expected = {
            "schema_version", "resource_id", "suppliers", "scenarios", "budget",
            "unit_cost", "procurement_limit", "demand", "base_fulfillment", "shortage_penalty",
        }
        _keys(payload, expected, "data schema")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("unsupported data schema_version")
        return cls(**{k: v for k, v in payload.items() if k != "schema_version"})

    @property
    def data_sha256(self) -> str:
        return canonical_json_sha256(self.to_dict())

    @property
    def scenario_sha256(self) -> str:
        return canonical_json_sha256({
            "resource_id": self.resource_id,
            "suppliers": list(self.suppliers),
            "ordered_scenarios": [
                {"id": w, "demand": self.demand[w], "base_fulfillment": dict(self.base_fulfillment[w])}
                for w in self.scenarios
            ],
        })
