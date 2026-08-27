"""Strict single-resource Reliability and F-OPTION extensions of frozen M0 data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .model_data import BudgetAllocationData, _ids, _keys, _number
from robust_budget_allocation.io.hashing import canonical_json_sha256


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return float(value)


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return list(value)
    return value


@dataclass(frozen=True)
class ReliabilityData:
    base: BudgetAllocationData
    levels: Mapping[str, tuple[str, ...]]
    fixed_premium: Mapping[str, Mapping[str, float]]
    unit_premium: Mapping[str, Mapping[str, float]]
    fulfillment: Mapping[str, Mapping[str, Mapping[str, float]]]

    def __post_init__(self):
        self.validate()
        object.__setattr__(self, "levels", MappingProxyType({j: tuple(ks) for j, ks in self.levels.items()}))
        for name in ("fixed_premium", "unit_premium", "fulfillment"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def validate(self):
        if not isinstance(self.base, BudgetAllocationData):
            raise ValueError("base must be frozen M0 BudgetAllocationData")
        self.base.validate()
        for name in ("levels", "fixed_premium", "unit_premium"):
            _keys(getattr(self, name), self.base.suppliers, name)
        _keys(self.fulfillment, self.base.scenarios, "fulfillment")
        for w in self.base.scenarios:
            _keys(self.fulfillment[w], self.base.suppliers, f"fulfillment[{w}]")
        for j in self.base.suppliers:
            ks = self.levels[j]
            _ids(ks, f"levels[{j}]")
            if ks[0] != "0":
                raise ValueError("base level '0' must be first in each declared weak order")
            for name in ("fixed_premium", "unit_premium"):
                values = getattr(self, name)[j]
                _keys(values, ks, f"{name}[{j}]")
                for k in ks:
                    _number(values[k], f"{name}[{j}][{k}]")
                if values["0"] != 0:
                    raise ValueError("base Reliability premium must equal zero")
                if any(values[b] < values[a] for a, b in zip(ks, ks[1:])):
                    raise ValueError("Reliability premiums must be weakly nondecreasing")
            for w in self.base.scenarios:
                values = self.fulfillment[w][j]
                _keys(values, ks, f"fulfillment[{w}][{j}]")
                for k in ks:
                    _number(values[k], f"fulfillment[{w}][{j}][{k}]", upper=1)
                if values["0"] != self.base.base_fulfillment[w][j]:
                    raise ValueError("base fulfillment must equal the shared M0 input")
                if any(values[b] < values[a] for a, b in zip(ks, ks[1:])):
                    raise ValueError("fulfillment must be weakly nondecreasing in every scenario")

    def to_dict(self):
        return {"schema_version": 1, "base": self.base.to_dict(),
                **{name: _plain(getattr(self, name))
                   for name in ("levels", "fixed_premium", "unit_premium", "fulfillment")}}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]):
        _keys(payload, {"schema_version", "base", "levels", "fixed_premium", "unit_premium", "fulfillment"}, "Reliability schema")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("unsupported Reliability schema version")
        return cls(base=BudgetAllocationData.from_dict(payload["base"]),
                   **{name: payload[name] for name in ("levels", "fixed_premium", "unit_premium", "fulfillment")})

    @property
    def data_sha256(self):
        return canonical_json_sha256(self.to_dict())

    @property
    def scenario_sha256(self):
        return self.base.scenario_sha256


@dataclass(frozen=True)
class OptionData:
    reliability: ReliabilityData
    option_fee: float
    option_cap: float
    emergency_price: Mapping[str, float]

    def __post_init__(self):
        self.validate()
        object.__setattr__(self, "option_fee", float(self.option_fee))
        object.__setattr__(self, "option_cap", float(self.option_cap))
        object.__setattr__(self, "emergency_price", _freeze(self.emergency_price))

    @property
    def base(self):
        return self.reliability.base

    def validate(self):
        if not isinstance(self.reliability, ReliabilityData):
            raise ValueError("reliability must be ReliabilityData")
        self.reliability.validate()
        for name in ("option_fee", "option_cap"):
            value = getattr(self, name)
            _number(value, name)
            if value <= 0:
                raise ValueError(f"{name} must be strictly positive")
        _keys(self.emergency_price, self.base.scenarios, "emergency_price")
        for w in self.base.scenarios:
            _number(self.emergency_price[w], f"emergency_price[{w}]")
            if self.emergency_price[w] <= 0:
                raise ValueError("emergency price must be strictly positive")

    def to_dict(self):
        return {"schema_version": 1, "reliability": self.reliability.to_dict(),
                "option_fee": self.option_fee, "option_cap": self.option_cap,
                "emergency_price": dict(self.emergency_price)}

    @classmethod
    def from_dict(cls, payload):
        _keys(payload, {"schema_version", "reliability", "option_fee", "option_cap", "emergency_price"}, "Option schema")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("unsupported Option schema version")
        return cls(ReliabilityData.from_dict(payload["reliability"]), payload["option_fee"],
                   payload["option_cap"], payload["emergency_price"])

    @property
    def data_sha256(self):
        return canonical_json_sha256(self.to_dict())

    @property
    def scenario_sha256(self):
        return self.base.scenario_sha256
