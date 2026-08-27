from dataclasses import FrozenInstanceError, replace
import math

import pytest

from robust_budget_allocation.data.model_data import BudgetAllocationData


@pytest.mark.parametrize("field", ["budget", "shortage_penalty"])
@pytest.mark.parametrize("bad", [-1, math.inf, math.nan, True, "1"])
def test_invalid_scalars(m0_data, field, bad):
    with pytest.raises(ValueError):
        replace(m0_data, **{field: bad})


@pytest.mark.parametrize("field", ["unit_cost", "procurement_limit", "demand"])
@pytest.mark.parametrize("bad", [-1, math.inf, math.nan, True])
def test_invalid_mapping_numbers(m0_data, field, bad):
    key = next(iter(getattr(m0_data, field)))
    with pytest.raises(ValueError):
        replace(m0_data, **{field: {key: bad}})


@pytest.mark.parametrize("bad", [-0.1, 1.1, math.inf, math.nan, False])
def test_invalid_base_fulfillment(m0_data, bad):
    with pytest.raises(ValueError):
        replace(m0_data, base_fulfillment={"scenario": {"supplier": bad}})


@pytest.mark.parametrize("field", ["unit_cost", "procurement_limit", "demand", "base_fulfillment"])
@pytest.mark.parametrize("bad", [{}, {"extra": 1}])
def test_keys_must_match_exactly(m0_data, field, bad):
    with pytest.raises(ValueError, match="keys"):
        replace(m0_data, **{field: bad})


def test_nested_supplier_keys_must_match(m0_data):
    with pytest.raises(ValueError, match="keys"):
        replace(m0_data, base_fulfillment={"scenario": {"wrong": 1}})


@pytest.mark.parametrize("field", ["suppliers", "scenarios"])
@pytest.mark.parametrize("bad", [(), ("a", "a"), {"a", "b"}, ("",), (2,)])
def test_ordered_nonempty_unique_identifiers(m0_data, field, bad):
    with pytest.raises(ValueError):
        replace(m0_data, **{field: bad})


def test_schema_roundtrip_and_hashes(m0_data):
    restored = BudgetAllocationData.from_dict(m0_data.to_dict())
    assert restored.to_dict() == m0_data.to_dict()
    assert restored.data_sha256 == m0_data.data_sha256
    assert restored.scenario_sha256 == m0_data.scenario_sha256
    changed = replace(m0_data, budget=99)
    assert changed.data_sha256 != m0_data.data_sha256
    assert changed.scenario_sha256 == m0_data.scenario_sha256


def test_input_defensive_copy_and_immutability(m0_data):
    payload = m0_data.to_dict()
    data = BudgetAllocationData.from_dict(payload)
    payload["base_fulfillment"]["scenario"]["supplier"] = 0
    payload["unit_cost"]["supplier"] = 999
    assert data.base_fulfillment["scenario"]["supplier"] == 1
    assert data.unit_cost["supplier"] == 2
    with pytest.raises(TypeError):
        data.base_fulfillment["scenario"]["supplier"] = 0
    with pytest.raises(FrozenInstanceError):
        data.budget = 0


def test_scenario_order_is_explicit_and_identity_sensitive(m0_data):
    data = replace(m0_data, scenarios=("b", "a"), demand={"a": 1, "b": 2},
                   base_fulfillment={"a": {"supplier": 1}, "b": {"supplier": 0.5}})
    reordered_maps = replace(data, demand={"b": 2, "a": 1})
    assert data.data_sha256 == reordered_maps.data_sha256
    assert data.scenarios == ("b", "a")
    assert data.scenario_sha256 != replace(data, scenarios=("a", "b")).scenario_sha256


def test_zero_boundary_and_unknown_fields(m0_data):
    replace(m0_data, budget=0, shortage_penalty=0).validate()
    payload = m0_data.to_dict()
    payload["extra_scientific_field"] = 1
    with pytest.raises(ValueError, match="keys"):
        BudgetAllocationData.from_dict(payload)
