from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY
from robust_budget_allocation.formal.e2a import (
    BUDGET,
    CASES,
    SAMPLE_SHA256,
    baseline_identity_preflight,
    data_for_case_sample,
    load_base_fixture,
    load_samples,
)
from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def test_e2a_preflight_rebuilds_all_1000_baseline_identities():
    report = baseline_identity_preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["sample_count"] == report["baseline_reused_count"] == 1000
    assert report["planned_new_runs"] == 4000
    assert report["algorithm_identity"] == FINAL_A1_IDENTITY
    assert report["E2_B_runs"] == report["E2_C_runs"] == report["E2_D_runs"] == 0


def test_e2a_frozen_sample_sha_and_cases():
    assert sha256_file(ROOT / "formal_results/e1_final/e1_samples.csv") == SAMPLE_SHA256
    assert CASES == {
        "E2A_VACCINE_H0": {"h_V_tau": 0.0, "a_C": 0.9},
        "E2A_VACCINE_H1": {"h_V_tau": 1.0, "a_C": 0.9},
        "E2A_CRACKERS_A100": {"h_V_tau": 0.5, "a_C": 1.0},
        "E2A_CRACKERS_A080": {"h_V_tau": 0.5, "a_C": 0.8},
    }


@pytest.mark.parametrize("case_id", tuple(CASES))
def test_e2a_ofat_data_changes_only_target_static_field(case_id):
    samples = load_samples(ROOT)
    payload, metadata = load_base_fixture(ROOT)
    baseline = data_for_case_sample(payload, metadata, "E2A_CRACKERS_A100", samples[0]).to_dict()
    baseline["retention"]["Crackers"] = 0.9
    tested = data_for_case_sample(payload, metadata, case_id, samples[0])
    assert tested.budget == BUDGET
    assert tested.storage_cost["Water"] == tested.storage_cost["Crackers"] == 0.0
    assert tested.retention["Water"] == tested.retention["Seasonal Influenza Vaccine"] == 1.0
    assert tested.storage_cost["Seasonal Influenza Vaccine"] * tested.tau == pytest.approx(CASES[case_id]["h_V_tau"])
    assert tested.retention["Crackers"] == CASES[case_id]["a_C"]
    candidate = tested.to_dict()
    candidate["storage_cost"] = baseline["storage_cost"]
    candidate["retention"] = baseline["retention"]
    assert candidate == baseline
