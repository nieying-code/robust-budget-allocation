import json
import math
from functools import lru_cache
from pathlib import Path

import pyomo.environ as pyo

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.data.qfr_r6c import (
    ACTIVE_ITEMS,
    build_revised_experiment_matrix,
    build_revised_formal_data,
    generate_synthetic_oos,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.models.qfr_m1 import build_qfr_m1
from robust_budget_allocation.models.qfr_m2 import build_qfr_m2


ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "configs/r6c_scientific_revision_v2.json"
READY = ROOT / "configs/r6c_formal_ready_data_v2.json"
CONFIG = ROOT / "configs/r6c_formal_experiment_matrix_v2.json"
EXPANDED = ROOT / "configs/r6c_formal_experiment_matrix_expanded_v2.json"
PROTECTION = ROOT / "docs/evidence/R6_C_OLD_R7_E1_PROTECTION.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _generated_data():
    return build_revised_formal_data(REVISION, ROOT)


@lru_cache(maxsize=1)
def _generated_matrix():
    return build_revised_experiment_matrix(CONFIG, ROOT)


def test_r6c_data_is_exact_deterministic_revised_identity():
    generated = _generated_data()
    assert generated == _load(READY)
    bare = dict(generated)
    digest = bare.pop("data_sha256")
    assert digest == "59f4b89d8706f9af06aef46455292335b8b8b095f4a2a0ce0f700e5d219ed16f"
    assert digest == canonical_json_sha256(bare)
    assert generated["scenario_sha256"] == "3bfea4bad74d39422eb4e004f4c5ffe883cffc7d65244ab14b2d87864531fede"
    assert generated["scientific_runs"] == 0


def test_r6c_data_structure_parameters_demand_fbar_and_budget():
    data = _generated_data()
    assert tuple(data["qfr_data"]["items"]) == ACTIVE_ITEMS
    assert data["scenario_counts"] == {"single": 15, "combined": 35, "no_hurricane": 1}
    assert len(data["scenarios"]) == 51
    assert math.isclose(sum(row["probability"] for row in data["scenarios"]), 1.0, abs_tol=1e-12)
    params = data["parameters"]
    assert params["q_unit_cost"] == {"Water": 0.6477, "Seasonal Influenza Vaccine": 13.916, "Crackers": 0.09372}
    assert params["storage_horizon_cost"]["Seasonal Influenza Vaccine"] == 0.5
    assert params["retention"] == {"Water": 1.0, "Seasonal Influenza Vaccine": 1.0, "Crackers": 0.9}
    assert params["q_survivability_cat1_to_cat5"] == [0.9, 0.85, 0.8, 0.75, 0.7]
    assert params["f_disruption_cat1_to_cat5"] == [0.1, 0.3, 0.6, 0.8, 1.0]
    assert params["reliability_mitigation"] == [0.2, 0.5, 0.8]
    assert params["reliability_cost_ratios"] == [0.0, 0.1, 0.25]
    assert params["shortage_priority_lambda"] == dict.fromkeys(ACTIVE_ITEMS, 1.0)
    assert params["shortage_cost"] == {item: 4.0 * params["q_unit_cost"][item] for item in ACTIVE_ITEMS}
    for item in ACTIVE_ITEMS:
        expected_max = max(params["shortage_cost"][item] * row["formal_demand"][item] for row in data["scenarios"])
        assert math.isclose(
            data["economic_scale_audit"]["shortage_exposure"]["absolute"][item]["max"],
            expected_max,
            rel_tol=0.0,
            abs_tol=1e-6,
        )
    first = data["scenarios"][0]
    assert first["formal_demand"]["Water"] == 350000.0
    assert math.isclose(first["formal_demand"]["Seasonal Influenza Vaccine"], (140 / 13.916) * 500, abs_tol=1e-10)
    assert first["formal_demand"]["Crackers"] == 14 * 1000 * 525
    for item in ACTIVE_ITEMS:
        assert data["flexible_capacity"][item] == max(row["formal_demand"][item] for row in data["scenarios"])
    assert data["reference_budget_regeneration"] == "RECOMPUTED_FROM_REVISED_FREEZE_INPUTS_NOT_CARRIED_FORWARD"
    assert math.isclose(data["reference_budget"], sum(data["reference_budget_components"].values()), abs_tol=1e-9)
    assert data["reference_budget"] == 7975014.2749022
    no_hurricane = next(row for row in data["scenarios"] if row["scenario_type"] == "no_hurricane")
    assert set(no_hurricane["formal_demand"].values()) == {0.0}
    assert (no_hurricane["q_availability"], no_hurricane["disruption"]) == (1.0, 0.0)


def test_r6c_m1_m2_mechanism_identity_without_solving():
    data = QFRData.from_dict(_generated_data()["qfr_data"])
    m1 = build_qfr_m1(data)
    m2 = build_qfr_m2(data)
    assert tuple(m1.R) == (0,)
    assert tuple(m2.R) == (0, 1, 2)
    for item in ACTIVE_ITEMS:
        assert data.reliability_cost[item][0] == 0.0
        assert [data.reliability_mitigation[item][level] for level in (0, 1, 2)] == [0.2, 0.5, 0.8]
    cat4 = next(row["scenario_id"] for row in _generated_data()["scenarios"] if row["category"] == 4)
    cat5 = next(row["scenario_id"] for row in _generated_data()["scenarios"] if row["category"] == 5)
    for item in ACTIVE_ITEMS:
        assert math.isclose(pyo.value(m1.rho[item, cat4, 0]), 1 - (1 - 0.2) * 0.8)
        assert math.isclose(pyo.value(m1.rho[item, cat5, 0]), 0.2)
        assert math.isclose(pyo.value(m2.rho[item, cat5, 2]), 0.8)


def test_r6c_matrix_e1_e2_e3_and_dedup_are_exact():
    config, matrix = _load(CONFIG), _generated_matrix()
    assert matrix == _load(EXPANDED)
    bare = dict(matrix)
    digest = bare.pop("matrix_sha256")
    assert digest == "4d676dba804a9a0e8cdd117b846388a5100e61c1ef57de01692e8834afb016c7"
    assert digest == canonical_json_sha256(bare)
    assert matrix["counts"] == {
        "E1": 9, "E2_families": 8, "E2_logical": 28, "E2_unique_physical": 21,
        "E3_I1": 9, "E3_I2": 9, "E3_unique_physical": 17,
        "E4_A_folds": 15, "E4_B_realizations_per_seed": 2000, "E4_B_seeds": 10,
        "E5_algorithm_cases": 27, "E5_planned_timing_runs": 81, "E5_timing_repetitions": 3,
    }
    assert matrix["deduplication"] == {
        "rule": "ONE_SOLVE_PER_PHYSICAL_CONFIGURATION_IDENTITY_WITH_ALL_LOGICAL_MEMBERSHIPS_RETAINED",
        "E2_logical": 28, "E2_unique_physical": 21, "E2_baseline_dedup_count": 7,
        "E3_logical": 18, "E3_unique_physical": 17, "E3_baseline_dedup_count": 1,
        "E1_E2_E3_logical": 55, "E1_E2_E3_unique_physical": 37,
    }
    families = config["E2"]["families"]
    assert list(families) == [
        "E2_1_vaccine_cold_chain", "E2_2_crackers_retention", "E2_3_f_price_split",
        "E2_4_r_premium", "E2_5_reliability_eta", "E2_6_f_disruption_delta",
        "E2_7_shortage_beta", "E2_8_commodity_priority_lambda",
    ]
    assert families["E2_5_reliability_eta"]["levels"] == [[0.1, 0.4, 0.7], [0.2, 0.5, 0.8], [0.3, 0.6, 0.9]]
    assert families["E2_6_f_disruption_delta"]["mapped_levels"] == [[0.08, 0.24, 0.48, 0.64, 0.8], [0.1, 0.3, 0.6, 0.8, 1.0], [0.12, 0.36, 0.72, 0.96, 1.0]]
    assert families["E2_8_commodity_priority_lambda"]["levels"] == [[1.0, 1.0, 1.0], [1.25, 1.0, 1.0], [1.5, 1.0, 1.0], [1.0, 1.25, 1.0], [1.0, 1.5, 1.0], [1.0, 1.0, 1.25], [1.0, 1.0, 1.5]]
    assert matrix["execution_counts"] == {"E1": 0, "E2": 0, "E3": 0, "E4": 0, "E5": 0, "formal_scientific_runs": 0}


def test_r6c_e4_e5_rules_and_synthetic_no_hurricane():
    config, matrix, formal = _load(CONFIG), _generated_matrix(), _generated_data()
    assert len(matrix["E4_A_folds"]) == 15
    assert len(matrix["E4_B_dataset_registry"]) == 10
    sample = generate_synthetic_oos(formal, config["E4"]["synthetic"], 61001)
    assert len(sample["rows"]) == 2000
    no_hurricane = [row for row in sample["rows"] if row["base_scenario_type"] == "no_hurricane"]
    assert no_hurricane
    for row in no_hurricane:
        assert set(row["demand"].values()) == {0.0}
        assert (row["q_availability"], row["disruption"]) == (1.0, 0.0)
    assert {row["algorithm"] for row in matrix["E5_algorithm_cases"]} == {"A0", "A1_no_memory", "A1_full"}
    assert sum(row["timing_repetitions"] for row in matrix["E5_algorithm_cases"]) == 81
    assert sum(row["actual_timing_runs"] for row in matrix["E5_algorithm_cases"]) == 0


def test_old_r7_e1_protection_manifest_matches_worktree():
    evidence = _load(PROTECTION)
    tracked = evidence["tracked_files"]
    assert len(tracked) == evidence["tracked_file_count"] == 14
    assert {row["path"] for row in tracked} == set(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "experiments/r7_e1").rglob("*") if path.is_file()
    )
    for row in tracked:
        assert sha256_file(ROOT / row["path"]) == row["sha256"]
    assert evidence["directory_diff_against_baseline"] == []
    assert evidence["old_r7_e1_evidence_unchanged"] == "PASS"
