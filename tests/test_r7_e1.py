from copy import deepcopy
from pathlib import Path

import pytest

from robust_budget_allocation.formal.e1 import (
    EXPECTED_BUDGETS,
    EXPECTED_ITEMS,
    EXPECTED_MODELS,
    _summary,
    _validate_e1_cases,
    _validate_ready_payload,
    build_case_data,
    initialize_output_root,
    load_authorities,
    replay_delivery,
    solver_free_preflight,
)


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_chain_and_solver_free_preflight_pass():
    authority = load_authorities(ROOT)
    report = solver_free_preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["scenario_count"] == 51
    assert tuple(report["commodities"]) == EXPECTED_ITEMS
    assert len(authority["cases"]) == report["e1_case_count"] == 9


def test_e1_is_exact_cartesian_matrix_without_other_families():
    cases = load_authorities(ROOT)["cases"]
    assert [(row["budget_ratio"], row["model_kind"]) for row in cases] == [
        (budget, model) for budget in EXPECTED_BUDGETS for model in EXPECTED_MODELS
    ]
    assert {row["family"] for row in cases} == {"E1"}


def test_case_data_changes_only_registered_budget():
    ready = load_authorities(ROOT)["ready"]
    original = deepcopy(ready["qfr_data"])
    for ratio in EXPECTED_BUDGETS:
        data = build_case_data(ready, ratio)
        candidate = data.to_dict()
        assert candidate.pop("budget") == pytest.approx(ready["reference_budget"] * ratio)
        expected = deepcopy(original)
        expected.pop("budget")
        assert candidate == expected


def test_negative_formal_data_identity_is_rejected():
    ready = deepcopy(load_authorities(ROOT)["ready"])
    ready["reference_budget"] += 1
    with pytest.raises(ValueError, match="identity mismatch"):
        _validate_ready_payload(ready)


def test_negative_case_count_and_contamination_are_rejected():
    cases = load_authorities(ROOT)["cases"]
    with pytest.raises(ValueError, match="exactly 9"):
        _validate_e1_cases(cases[:-1])
    contaminated = deepcopy(cases)
    contaminated[0]["family"] = "E2"
    with pytest.raises(ValueError, match="contamination"):
        _validate_e1_cases(contaminated)


def test_output_root_creation_is_atomic_scope_and_never_overwrites(tmp_path):
    output = tmp_path / "r7_e1"
    initialize_output_root(output)
    assert (output / "raw").is_dir()
    with pytest.raises(FileExistsError, match="already exists"):
        initialize_output_root(output)


def test_summary_rejects_incomplete_cases():
    assert _summary([])["status"] == "FAIL"
    assert _summary([])["formal_scientific_runs"] == 0


def test_execution_policy_has_no_e5_ablation_or_timing_repetitions():
    execution = load_authorities(ROOT)["execution"]
    assert execution["certification_chain"] == ["EF", "A0", "A1_full"]
    assert execution["a1_memory_phase_enabled"] is True
    assert execution["timing_protocol"] == "NO_TIMING_REPETITIONS_E1"
    assert "A1_no_memory" not in str(execution)


def test_committed_r7_e1_delivery_replays():
    assert replay_delivery(ROOT) == {
        "status": "PASS",
        "case_count": 9,
        "certificate_pass_count": 9,
        "manifest_sha256": "177485800b5bbc50fe15e0e1d13a6188a5c6d617ba889207815ba7d5c79a6780",
        "summary_sha256": "0f57260985ed97d677860f99fc71fae8c9c39838d13db2ddefa5a62dc259bfd6",
    }
