from copy import deepcopy
import json
from pathlib import Path

import pytest

from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "r2_qfr_test_fixture.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def payload():
    return deepcopy(FIXTURE["data"])


def test_three_item_fixture_is_explicitly_nonformal_and_roundtrips():
    assert FIXTURE["fixture_scope"] == "TEST_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS"
    data = QFRData.from_dict(payload())
    assert data.items == ("ordinary", "preservation_sensitive", "perishable")
    assert data.scenarios == ("moderate", "severe")
    assert RELIABILITY_LEVELS == (0, 1, 2)
    assert QFRData.from_dict(data.to_dict()).to_dict() == data.to_dict()
    assert QFRData.from_dict(data.to_dict()).data_sha256 == data.data_sha256


def test_schema_is_deeply_immutable():
    data = QFRData.from_dict(payload())
    with pytest.raises(TypeError):
        data.demand["moderate"]["ordinary"] = 99
    with pytest.raises(TypeError):
        data.reliability_cost["ordinary"][1] = 99


def test_scenario_identity_covers_ordered_items_demand_and_disruption():
    original = QFRData.from_dict(payload())
    changed_demand = payload()
    changed_demand["demand"]["moderate"]["ordinary"] += 1
    changed_disruption = payload()
    changed_disruption["disruption"]["severe"]["perishable"] = 0.9
    reordered = payload()
    reordered["scenarios"] = list(reversed(reordered["scenarios"]))
    assert QFRData.from_dict(changed_demand).scenario_sha256 != original.scenario_sha256
    assert QFRData.from_dict(changed_disruption).scenario_sha256 != original.scenario_sha256
    assert QFRData.from_dict(reordered).scenario_sha256 != original.scenario_sha256


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("budget", -1),
        ("tau", -1),
        ("q_unit_cost", 0),
        ("storage_cost", -1),
        ("retention", 0),
        ("retention", 1.1),
        ("flexible_capacity", -1),
        ("reservation_cost", 0),
        ("exercise_cost", 0),
        ("shortage_cost", 0),
        ("demand", -1),
        ("disruption", -0.1),
        ("disruption", 1.1),
    ],
)
@pytest.mark.parametrize("nonfinite", [False, True])
def test_numeric_domains_reject_invalid_values(field, bad, nonfinite):
    candidate = payload()
    value = float("nan") if nonfinite else bad
    if field in {"budget", "tau"}:
        candidate[field] = value
    elif field in {"demand", "disruption"}:
        candidate[field]["moderate"]["ordinary"] = value
    else:
        candidate[field]["ordinary"] = value
    with pytest.raises(ValueError):
        QFRData.from_dict(candidate)


@pytest.mark.parametrize("bad", [True, float("inf"), float("-inf")])
def test_all_numbers_must_be_finite_non_boolean_reals(bad):
    candidate = payload()
    candidate["q_unit_cost"]["ordinary"] = bad
    with pytest.raises(ValueError):
        QFRData.from_dict(candidate)


@pytest.mark.parametrize(
    ("field", "level", "bad"),
    [
        ("reliability_mitigation", "0", 0.1),
        ("reliability_mitigation", "1", 0),
        ("reliability_mitigation", "2", 1),
        ("reliability_mitigation", "2", 0.3),
        ("reliability_cost", "0", 0.1),
        ("reliability_cost", "1", 0),
        ("reliability_cost", "2", 0.3),
    ],
)
def test_strict_reliability_ordering(field, level, bad):
    candidate = payload()
    candidate[field]["ordinary"][level] = bad
    with pytest.raises(ValueError):
        QFRData.from_dict(candidate)


@pytest.mark.parametrize(
    "mutation",
    ["missing_item", "extra_item", "missing_scenario", "missing_level", "wrong_levels"],
)
def test_exact_item_scenario_and_level_coverage(mutation):
    candidate = payload()
    if mutation == "missing_item":
        del candidate["retention"]["perishable"]
    elif mutation == "extra_item":
        candidate["storage_cost"]["extra"] = 1
    elif mutation == "missing_scenario":
        del candidate["demand"]["severe"]
    elif mutation == "missing_level":
        del candidate["reliability_cost"]["ordinary"]["2"]
    else:
        candidate["reliability_levels"] = [0, 1]
    with pytest.raises(ValueError):
        QFRData.from_dict(candidate)


def test_unknown_or_missing_schema_fields_are_rejected():
    extra = payload()
    extra["supplier"] = "not-permitted"
    missing = payload()
    del missing["tau"]
    with pytest.raises(ValueError):
        QFRData.from_dict(extra)
    with pytest.raises(ValueError):
        QFRData.from_dict(missing)
