from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qfr_mechanism_layer_a_t1 import (  # noqa: E402
    FAILURE_IDS,
    classify_outcomes,
    extract_a1_failure,
)


def test_exact_frozen_failure_ids():
    assert FAILURE_IDS == (
        "LA-0034", "LA-0098", "LA-0161", "LA-0511",
        "LA-0565", "LA-0591", "LA-0695", "LA-0783",
    )


@pytest.mark.parametrize(
    ("a1", "a0", "ef", "expected"),
    [
        ("oracle_failure", "certified", "optimal", "A1_ROBUSTNESS_ISSUE"),
        ("oracle_failure", "oracle_failure", "failed", "MODEL_SOLVER_NUMERICAL_OR_FEASIBILITY_ISSUE"),
        ("certified", "certified", "optimal", "OTHER_COMBINATION_REVIEW_REQUIRED"),
        ("oracle_failure", "certified", "failed", "OTHER_COMBINATION_REVIEW_REQUIRED"),
    ],
)
def test_outcome_classification(a1, a0, ef, expected):
    assert classify_outcomes(a1, a0, ef) == expected


def test_extract_candidate_failure_identity():
    result = {
        "status": "oracle_failure",
        "diagnostic": "Candidate exact evaluation failed",
        "result_sha256": "result-hash",
        "trace": [{
            "iteration": 2,
            "memory": {"status": "complete", "evaluations": []},
            "candidate": {
                "status": "oracle_failure",
                "planned": ["omega_02", "omega_03"],
                "evaluations": [{
                    "scenario_id": "omega_03",
                    "scenario_identity": "scenario-hash",
                    "first_stage_sha256": "first-stage-hash",
                    "solver": {
                        "status": "solver_error",
                        "termination_condition": "error",
                        "message": "message",
                        "runtime_seconds": 0.1,
                    },
                }],
            },
        }],
    }
    observed = extract_a1_failure(result)
    assert observed["phase"] == "candidate"
    assert observed["failing_scenario"] == "omega_03"
    assert observed["failing_scenario_identity"] == "scenario-hash"
    assert observed["failing_first_stage_sha256"] == "first-stage-hash"
    assert observed["solver_status"] == "solver_error"
    assert observed["solver_termination"] == "error"
