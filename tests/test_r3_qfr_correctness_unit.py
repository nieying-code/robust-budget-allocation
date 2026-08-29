from copy import deepcopy
import json
from pathlib import Path

import pyomo.environ as pyo
from pyomo.repn import generate_standard_repn
import pytest

from robust_budget_allocation.algorithms.qfr_builders import build_qfr_extensive_form
from robust_budget_allocation.algorithms.qfr_correctness_suite import load_fixture
from robust_budget_allocation.algorithms.qfr_exact_oracle import build_exact_recourse
from robust_budget_allocation.algorithms.qfr_protocol import (
    PROTOCOL_SHA256,
    canonical_scenarios,
    protocol_identity,
    scenario_identity,
    static_data_sha256,
    subset_data,
    tolerance,
)
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.algorithms.qfr_state import (
    QFRFirstStage,
    first_stage_cost,
    levels_for_kind,
    validate_first_stage,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/r3_correctness_v2.json"
PROTOCOL_PATH = ROOT / "docs/R3_CORRECTNESS_PROTOCOL_v2.md"
PAYLOAD = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def data() -> QFRData:
    return QFRData.from_dict(PAYLOAD["cases"][0]["data"])


def zero_decision(data: QFRData, kind: str) -> QFRFirstStage:
    levels = levels_for_kind(kind)
    return QFRFirstStage(
        model_kind=kind,
        reliability_levels=levels,
        data_sha256=data.data_sha256,
        scenario_sha256=data.scenario_sha256,
        static_data_sha256=static_data_sha256(data),
        q={item: 0.0 for item in data.items},
        f={item: {level: 0.0 for level in levels} for item in data.items},
        z={item: {level: 0 for level in levels} for item in data.items},
    )


def test_protocol_was_frozen_with_authorized_identity():
    assert sha256_file(PROTOCOL_PATH) == PROTOCOL_SHA256
    identity = protocol_identity(ROOT)
    assert identity["authority"] == "EXPLICITLY_RE_REGISTERED_FOR_R3_V2_CORRECTNESS"
    assert identity["freeze_commit"] == "c29a67c1369f44c4afb424c0ba2a8b0d43a0b923"
    assert tolerance(0, 0) == pytest.approx(1.01e-7)
    assert tolerance(-1000, 2) == pytest.approx(1.1e-6)
    with pytest.raises(ValueError):
        tolerance(float("nan"), 0)


def test_preregistered_fixture_is_v2_multi_item_and_not_scientific_parameters(data):
    loaded = load_fixture(FIXTURE_PATH)
    assert loaded["fixture_scope"] == "CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS"
    assert len(data.items) == 3
    assert canonical_scenarios(data) == (
        "a_zero_disruption",
        "b_disrupted",
        "c_peak",
    )
    assert all(data.disruption["a_zero_disruption"][item] == 0 for item in data.items)
    assert any(data.disruption["c_peak"][item] > 0 for item in data.items)


def test_subset_preserves_static_science_but_has_complete_restricted_identity(data):
    restricted = subset_data(data, ("a_zero_disruption", "c_peak"))
    assert static_data_sha256(restricted) == static_data_sha256(data)
    assert restricted.data_sha256 != data.data_sha256
    assert restricted.scenario_sha256 != data.scenario_sha256
    assert scenario_identity(restricted, "c_peak") == scenario_identity(data, "c_peak")


def test_scenario_identity_uses_demand_disruption_and_static_data(data):
    original = scenario_identity(data, "b_disrupted")
    changed = deepcopy(PAYLOAD["cases"][0]["data"])
    changed["disruption"]["b_disrupted"]["ordinary"] += 0.1
    assert scenario_identity(QFRData.from_dict(changed), "b_disrupted") != original
    changed = deepcopy(PAYLOAD["cases"][0]["data"])
    changed["demand"]["b_disrupted"]["ordinary"] += 1
    assert scenario_identity(QFRData.from_dict(changed), "b_disrupted") != original
    changed = deepcopy(PAYLOAD["cases"][0]["data"])
    changed["retention"]["ordinary"] -= 0.05
    assert scenario_identity(QFRData.from_dict(changed), "b_disrupted") != original


@pytest.mark.parametrize("kind", ["M0", "M1", "M2"])
def test_extensive_form_is_exactly_reviewed_r2_full_scenario_builder(data, kind):
    model = build_qfr_extensive_form(data, kind)
    assert tuple(model.I) == data.items
    assert tuple(model.Omega) == data.scenarios
    assert model._qfr_data_sha256 == data.data_sha256
    assert model._qfr_scenario_sha256 == data.scenario_sha256
    assert model._qfr_kind == kind


@pytest.mark.parametrize("kind", ["M0", "M1", "M2"])
def test_exact_recourse_has_only_second_stage_variables_and_fixed_budget_accounting(data, kind):
    decision = zero_decision(data, kind)
    model = build_exact_recourse(data, decision, "c_peak")
    variables = set(model.component_map(pyo.Var))
    assert variables == ({"u"} if kind == "M0" else {"u", "x"})
    assert not any(name in variables for name in {"Q", "F", "z", "theta"})
    repn = generate_standard_repn(model.total_cost.expr)
    assert repn.is_linear()
    coefficients = {
        variable.name: float(coefficient)
        for variable, coefficient in zip(repn.linear_vars, repn.linear_coefs, strict=True)
    }
    for item in data.items:
        assert coefficients[f"u[{item}]"] == pytest.approx(data.shortage_cost[item])
        if kind != "M0":
            assert coefficients[f"x[{item}]"] == pytest.approx(data.exercise_cost[item])
    if kind == "M0":
        assert not hasattr(model, "fixed_total_budget")
    else:
        budget = generate_standard_repn(model.fixed_total_budget.body)
        budget_coefficients = {
            variable.name: float(coefficient)
            for variable, coefficient in zip(
                budget.linear_vars, budget.linear_coefs, strict=True
            )
        }
        assert not any(name.startswith("u[") for name in budget_coefficients)
        assert all(f"x[{item}]" in budget_coefficients for item in data.items)


def test_first_stage_rejects_wrong_hash_capacity_or_reliability(data):
    decision = zero_decision(data, "M2")
    assert first_stage_cost(data, decision) == pytest.approx(0)
    assert validate_first_stage(data, decision) == pytest.approx(0)
    wrong_hash = QFRFirstStage(**{**decision.__dict__, "scenario_sha256": "0" * 64})
    with pytest.raises(ValueError, match="identity"):
        validate_first_stage(data, wrong_hash)
    over_capacity = deepcopy(decision.to_dict())
    over_capacity["f"]["ordinary"]["0"] = data.flexible_capacity["ordinary"] + 1
    over_capacity["z"]["ordinary"]["0"] = 1
    with pytest.raises(ValueError, match="Fbar"):
        validate_first_stage(data, QFRFirstStage.from_dict(over_capacity))
    multi_level = deepcopy(decision.to_dict())
    multi_level["z"]["ordinary"]["0"] = 1
    multi_level["z"]["ordinary"]["1"] = 1
    with pytest.raises(ValueError, match="multiple reliability"):
        validate_first_stage(data, QFRFirstStage.from_dict(multi_level))


def test_a0_rejects_unfrozen_iteration_limits_without_solving(data):
    for value in (0, -1, 5, 1.5, True):
        with pytest.raises(ValueError, match="maximum_iterations"):
            solve_qfr_standard_ccg(data, "M0", maximum_iterations=value)


def test_a0_source_has_no_a1_memory_or_candidate_dependency():
    source = (ROOT / "src/robust_budget_allocation/algorithms/qfr_standard_ccg.py").read_text(
        encoding="utf-8"
    )
    assert "memory_guided" not in source
    assert "a1_" not in source.lower()
    assert "candidate ranking" not in source.lower()
