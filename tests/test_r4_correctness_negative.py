"""Focused solver-free tests for R4 model and certification identity chains."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_a1_verification import (
    validate_improved_ccg_result,
    validate_three_certificate,
    verify_ef_a0_a1,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
INITIAL = json.loads(
    (ROOT / "docs/evidence/R4_A1_INITIAL_MEMORY_TRAJECTORY_v2.json").read_text(
        encoding="utf-8"
    )
)
FIXTURE_CASES = {
    row["case_id"]: row for row in INITIAL["fixture"]["payload"]["cases"]
}


def reseal(payload, key):
    payload.pop(key, None)
    payload[key] = canonical_json_sha256(payload)


def upgraded_case(kind):
    row = deepcopy(next(value for value in INITIAL["cases"] if value["model_kind"] == kind))
    a1 = row["a1"]
    for trace in a1["trace"]:
        certification = trace["full_exact_certification"]
        trace["full_exact_certification_iteration"] = (
            trace["iteration"] if certification is not None else None
        )
        if certification is None:
            trace["UB"] = None
            trace["incumbent_iteration"] = None
            trace["convergence"] = None
    reseal(a1, "result_sha256")
    data = QFRData.from_dict(FIXTURE_CASES[row["case_id"]]["data"])
    row["certificate"] = verify_ef_a0_a1(data, row["ef"], row["a0"], a1)
    return data, row


def test_cross_model_a1_substitution_is_rejected_even_when_objectives_match():
    data, m1 = upgraded_case("M1")
    _, m0 = upgraded_case("M0")
    with pytest.raises(ValueError, match="model-kind"):
        verify_ef_a0_a1(data, m1["ef"], m1["a0"], m0["a1"])


def test_outer_internal_and_certificate_model_kind_chain_is_closed():
    data, row = upgraded_case("M1")
    validate_three_certificate(
        data,
        row["ef"],
        row["a0"],
        row["a1"],
        row["certificate"],
        expected_model_kind="M1",
    )
    with pytest.raises(ValueError, match="model-kind"):
        validate_three_certificate(
            data,
            row["ef"],
            row["a0"],
            row["a1"],
            row["certificate"],
            expected_model_kind="M0",
        )
    tampered = deepcopy(row["certificate"])
    tampered["model_kind"] = "M0"
    reseal(tampered, "certificate_sha256")
    with pytest.raises(ValueError, match="model-kind"):
        validate_three_certificate(
            data,
            row["ef"],
            row["a0"],
            row["a1"],
            tampered,
            expected_model_kind="M1",
        )


@pytest.mark.parametrize(
    "field", ["ef_result_sha256", "a0_result_sha256", "a1_result_sha256"]
)
def test_certificate_rejects_wrong_result_binding(field):
    data, row = upgraded_case("M2")
    tampered = deepcopy(row["certificate"])
    tampered[field] = "0" * 64
    reseal(tampered, "certificate_sha256")
    with pytest.raises(ValueError, match="result binding"):
        validate_three_certificate(
            data,
            row["ef"],
            row["a0"],
            row["a1"],
            tampered,
            expected_model_kind="M2",
        )


def certification_row(a1):
    return next(row for row in a1["trace"] if row["full_exact_certification"] is not None)


def test_full_exact_theta_must_match_same_iteration_master_theta():
    data, row = upgraded_case("M0")
    trace = certification_row(row["a1"])
    oracle = trace["full_exact_certification"]
    oracle["theta"] += 1
    oracle["violation"] = max(0.0, oracle["worst_loss"] - oracle["theta"])
    reseal(oracle, "oracle_sha256")
    reseal(row["a1"], "result_sha256")
    with pytest.raises(ValueError, match="theta"):
        validate_improved_ccg_result(data, row["a1"])


def test_full_exact_certification_is_bound_to_its_iteration():
    data, row = upgraded_case("M1")
    trace = certification_row(row["a1"])
    trace["full_exact_certification_iteration"] = trace["iteration"] - 1
    reseal(row["a1"], "result_sha256")
    with pytest.raises(ValueError, match="iteration binding"):
        validate_improved_ccg_result(data, row["a1"])


def test_retained_ub_owner_must_match_certifying_iteration():
    data, row = upgraded_case("M2")
    trace = certification_row(row["a1"])
    trace["incumbent_iteration"] = 1
    reseal(row["a1"], "result_sha256")
    with pytest.raises(ValueError, match="ownership"):
        validate_improved_ccg_result(data, row["a1"])


def test_partial_iteration_cannot_claim_formal_ub_or_convergence():
    data, row = upgraded_case("M0")
    trace = next(value for value in row["a1"]["trace"] if value["candidate"]["hit"])
    trace["UB"] = row["a1"]["objective"]
    trace["incumbent_iteration"] = trace["iteration"]
    trace["convergence"] = True
    reseal(row["a1"], "result_sha256")
    with pytest.raises(ValueError, match="formal UB"):
        validate_improved_ccg_result(data, row["a1"])
