from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from robust_budget_allocation.data.mechanism_data import OptionData, ReliabilityData


CASES = json.loads((Path(__file__).parent / "fixtures/n3_mechanisms.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("path", [
    ("option_fee",), ("option_cap",), ("emergency_price", "w"),
    ("reliability", "base", "shortage_penalty"),
])
@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan"), True])
def test_strict_positive_domains(path, bad):
    payload = deepcopy(CASES[1]["data"])
    node = payload
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = bad
    with pytest.raises(ValueError):
        OptionData.from_dict(payload)


@pytest.mark.parametrize("name", ["fixed_premium", "unit_premium"])
@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True])
def test_invalid_premiums(name, bad):
    payload = deepcopy(CASES[1]["data"])
    payload["reliability"][name]["supplier"]["1"] = bad
    with pytest.raises(ValueError):
        OptionData.from_dict(payload)


@pytest.mark.parametrize("bad", [-.1, 1.1, float("inf"), float("nan"), True])
def test_invalid_fulfillment(bad):
    payload = deepcopy(CASES[1]["data"])
    payload["reliability"]["fulfillment"]["w"]["supplier"]["1"] = bad
    with pytest.raises(ValueError):
        OptionData.from_dict(payload)


@pytest.mark.parametrize("violation", ["base_fee", "base_unit", "base_fulfillment", "fulfillment_decrease",
    "fee_decrease", "unit_decrease", "level_missing", "level_extra", "unordered_levels", "base_missing",
    "supplier_missing", "scenario_missing", "price_missing"])
def test_domain_and_key_conflicts_rejected(violation):
    payload = deepcopy(CASES[1]["data"])
    rel = payload["reliability"]
    if violation == "base_fee": rel["fixed_premium"]["supplier"]["0"] = 1
    if violation == "base_unit": rel["unit_premium"]["supplier"]["0"] = 1
    if violation == "base_fulfillment": rel["fulfillment"]["w"]["supplier"]["0"] = .4
    if violation == "fulfillment_decrease": rel["fulfillment"]["w"]["supplier"]["1"] = .4
    if violation in ("fee_decrease", "unit_decrease"):
        payload = deepcopy(next(c for c in CASES if c["id"] == "arbitrary_four_levels")["data"])
        name = "fixed_premium" if violation == "fee_decrease" else "unit_premium"
        payload["reliability"][name]["supplier"]["gold"] = 0
    if violation == "level_missing": del rel["fixed_premium"]["supplier"]["1"]
    if violation == "level_extra": rel["unit_premium"]["supplier"]["extra"] = 1
    if violation == "unordered_levels": rel["levels"]["supplier"] = {"0", "1"}
    if violation == "base_missing": rel["levels"]["supplier"] = ["1"]
    if violation == "supplier_missing": rel["levels"] = {}
    if violation == "scenario_missing": rel["fulfillment"] = {}
    if violation == "price_missing": payload["emergency_price"] = {}
    with pytest.raises(ValueError):
        OptionData.from_dict(payload)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_roundtrip_shared_base_and_identity(case):
    data = OptionData.from_dict(case["data"])
    assert OptionData.from_dict(data.to_dict()).data_sha256 == data.data_sha256
    assert ReliabilityData.from_dict(data.reliability.to_dict()).data_sha256 == data.reliability.data_sha256
    assert data.base is data.reliability.base
    assert data.scenario_sha256 == data.reliability.scenario_sha256 == data.base.scenario_sha256
    assert replace(data, option_fee=data.option_fee + 1).data_sha256 != data.data_sha256


def test_weak_monotonicity_allows_equal_levels_and_no_limit_on_level_count():
    payload = deepcopy(CASES[0]["data"])
    rel = payload["reliability"]
    ks = ["0"] + [f"level_{i}" for i in range(1, 9)]
    rel["levels"]["supplier"] = ks
    rel["fixed_premium"]["supplier"] = {k: 0 for k in ks}
    rel["unit_premium"]["supplier"] = {k: 0 for k in ks}
    rel["fulfillment"]["w"]["supplier"] = {k: 1 for k in ks}
    data = OptionData.from_dict(payload)
    assert len(data.reliability.levels["supplier"]) == 9
    payload["reliability"]["fixed_premium"]["supplier"]["level_1"] = 999
    assert data.reliability.fixed_premium["supplier"]["level_1"] == 0
    with pytest.raises(TypeError):
        data.reliability.fulfillment["w"]["supplier"]["0"] = 0


def test_scenario_order_explicit():
    data = OptionData.from_dict(next(c for c in CASES if c["id"] == "unused_resource")["data"])
    rel = replace(data.reliability, base=replace(data.base, scenarios=tuple(reversed(data.base.scenarios))))
    assert replace(data, reliability=rel).scenario_sha256 != data.scenario_sha256
