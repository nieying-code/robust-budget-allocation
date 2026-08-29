from copy import deepcopy
import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_verification import validate_r3_evidence
from robust_budget_allocation.io.hashing import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs/evidence/R3_CORRECTNESS_FIRST_RUN_v2.json"


def load_evidence():
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def reseal(payload, key):
    payload.pop(key, None)
    payload[key] = canonical_json_sha256(payload)


def reseal_top(evidence):
    reseal(evidence, "evidence_sha256")


def reseal_a0_case(case):
    reseal(case["a0"], "result_sha256")
    case["certificate"]["a0_result_sha256"] = case["a0"]["result_sha256"]
    reseal(case["certificate"], "certificate_sha256")


def reseal_ef_case(case):
    reseal(case["ef"], "result_sha256")
    case["certificate"]["ef_result_sha256"] = case["ef"]["result_sha256"]
    reseal(case["certificate"], "certificate_sha256")


def test_first_run_evidence_replays_from_anchored_execution_commit():
    result = validate_r3_evidence(ROOT, load_evidence())
    assert result["status"] == "PASS"
    assert result["case_count"] == 3


@pytest.mark.parametrize(
    "attack",
    [
        "source_hash",
        "protocol_hash",
        "data_hash",
        "scenario_hash",
        "demand_same_index",
        "disruption_same_index",
        "static_item_parameter",
        "ef_objective",
        "lb_history",
        "scenario_addition_order",
        "missing_exact_oracle",
        "false_convergence",
        "wrong_solver_status",
        "missing_required_audit_field",
    ],
)
def test_resealed_integrity_attacks_fail_closed(attack):
    evidence = deepcopy(load_evidence())
    case = evidence["cases"][0]
    if attack == "source_hash":
        evidence["source"]["files"][0]["sha256"] = "0" * 64
    elif attack == "protocol_hash":
        evidence["protocol"]["sha256"] = "1" * 64
    elif attack == "data_hash":
        case["data_sha256"] = "2" * 64
    elif attack == "scenario_hash":
        case["scenario_sha256"] = "3" * 64
    elif attack in {"demand_same_index", "disruption_same_index", "static_item_parameter"}:
        fixture_case = evidence["fixture"]["payload"]["cases"][0]["data"]
        if attack == "demand_same_index":
            fixture_case["demand"]["b_disrupted"]["ordinary"] += 1
        elif attack == "disruption_same_index":
            fixture_case["disruption"]["b_disrupted"]["ordinary"] += 0.1
        else:
            fixture_case["retention"]["ordinary"] -= 0.05
        evidence["fixture"]["config_sha256"] = canonical_json_sha256(
            evidence["fixture"]["payload"]
        )
    elif attack == "ef_objective":
        case["ef"]["objective"] += 1
        reseal_ef_case(case)
    elif attack == "lb_history":
        case["a0"]["trace"][0]["LB"] += 1
        reseal_a0_case(case)
    elif attack == "scenario_addition_order":
        case["a0"]["trace"][0]["added_scenario"] = "b_disrupted"
        reseal_a0_case(case)
    elif attack == "missing_exact_oracle":
        case["a0"]["trace"][0]["oracle"].pop("results")
        reseal(case["a0"]["trace"][0]["oracle"], "oracle_sha256")
        reseal_a0_case(case)
    elif attack == "false_convergence":
        case["a0"]["trace"][-1]["convergence"] = False
        reseal_a0_case(case)
    elif attack == "wrong_solver_status":
        case["a0"]["trace"][0]["master"]["solver"]["solver_status"] = "warning"
        reseal_a0_case(case)
    else:
        evidence.pop("environment")
    reseal_top(evidence)
    with pytest.raises(ValueError):
        validate_r3_evidence(ROOT, evidence)
