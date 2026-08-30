"""Focused R4 A1 state, deterministic search, and correctness tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_a1_candidates import candidate_plan
from robust_budget_allocation.algorithms.qfr_a1_memory import QFRScenarioMemory
from robust_budget_allocation.algorithms.qfr_a1_verification import verify_ef_a0_a1
from robust_budget_allocation.algorithms.qfr_extensive_form import solve_qfr_extensive_form
from robust_budget_allocation.algorithms.qfr_improved_ccg import (
    R4_PROTOCOL_SHA256,
    a1_settings,
    solve_qfr_improved_ccg,
)
from robust_budget_allocation.algorithms.qfr_protocol import scenario_identities
from robust_budget_allocation.algorithms.qfr_standard_ccg import solve_qfr_standard_ccg
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/r3_correctness_v2.json").read_text(encoding="utf-8")
)


@pytest.fixture
def data() -> QFRData:
    return QFRData.from_dict(FIXTURE["cases"][0]["data"])


def test_r4_protocol_and_model_independent_candidate_rule(data):
    assert sha256_file(ROOT / "docs/R4_A1_PROTOCOL_v2.md") == R4_PROTOCOL_SHA256
    plan = candidate_plan(data, ["a_zero_disruption"], ["b_disrupted"])
    assert plan["planned"] == ["c_peak"]
    assert plan["ranking_rule"] == "CANONICAL_SCENARIO_ID_ONLY"
    assert "score" not in json.dumps(plan).lower()
    assert a1_settings(memory_phase_enabled=True)["cross_solve_memory"] is False


def test_memory_is_solve_local_bounded_deterministic_and_identity_bound(data):
    identities = scenario_identities(data)
    memory = QFRScenarioMemory(data.data_sha256, identities)
    assert memory.snapshot() == []
    rows = []
    for index, scenario in enumerate(data.scenarios):
        rows.append(
            {
                "scenario_id": scenario,
                "scenario_identity": identities[scenario],
                "solver": {"status": "optimal"},
                "loss": float(index + 1),
            }
        )
    memory.update(rows, 1, "EXACT")
    assert memory.prune(2) == []
    assert memory.inspection_plan(["c_peak"])["planned"] == ["b_disrupted", "a_zero_disruption"]
    copied = memory.snapshot()
    copied[0]["last_loss"] = 999
    assert memory.snapshot()[0]["last_loss"] != 999


@pytest.mark.parametrize("value", [0, -1, 5, 1.5, True])
def test_a1_rejects_invalid_iteration_limits_without_solving(data, value):
    with pytest.raises(ValueError, match="maximum_iterations"):
        solve_qfr_improved_ccg(data, "M0", maximum_iterations=value)


@pytest.mark.gurobi
@pytest.mark.parametrize("model_kind", ["M0", "M1", "M2"])
def test_provisional_ef_a0_a1_correctness(data, model_kind):
    ef = solve_qfr_extensive_form(data, model_kind)
    a0 = solve_qfr_standard_ccg(data, model_kind)
    a1 = solve_qfr_improved_ccg(data, model_kind, memory_phase_enabled=True)
    certificate = verify_ef_a0_a1(data, ef, a0, a1)
    assert certificate["status"] == "PASS"
