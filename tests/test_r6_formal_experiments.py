import json
import math
from pathlib import Path

from robust_budget_allocation.algorithms.qfr_improved_ccg import a1_settings
from robust_budget_allocation.data.qfr_formal_experiments import (
    FORMAL_DATA_SHA256,
    _draw_truncated_normal,
    build_experiment_matrix,
    generate_synthetic_oos,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/r6_formal_experiment_matrix_v1.json"
EXPANDED = ROOT / "configs/r6_formal_experiment_matrix_expanded_v1.json"
FORMAL_DATA = ROOT / "configs/r6_formal_ready_data_v1.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _matrix():
    return build_experiment_matrix(CONFIG, ROOT)


def test_r6b_identity_baseline_and_e1_are_frozen():
    config, matrix = _load(CONFIG), _matrix()
    assert config["formal_ready_data_sha256"] == FORMAL_DATA_SHA256
    assert config["scientific_runs"] == matrix["scientific_runs"] == 0
    assert config["r7_started"] is matrix["r7_started"] is False
    assert config["baseline"]["items"] == ["Water", "Seasonal Influenza Vaccine", "Crackers"]
    assert config["baseline"]["q_survivability_cat1_to_cat5"] == [0.9, 0.85, 0.8, 0.75, 0.7]
    assert config["baseline"]["f_disruption_cat1_to_cat5"] == [0.1, 0.3, 0.6, 1.0, 1.0]
    assert config["baseline"]["eta"] == [0.0, 0.5, 0.8]
    assert config["baseline"]["reliability_premium_ratios"] == [0.0, 0.1, 0.25]
    assert (config["baseline"]["phi"], config["baseline"]["psi"]) == (0.2, 0.85)
    assert len(matrix["E1_cases"]) == 9
    assert {(row["model_kind"], row["budget_ratio"]) for row in matrix["E1_cases"]} == {
        (model, budget) for model in ("M0", "M1", "M2") for budget in (0.9, 1.0, 1.1)
    }
    assert all(row["data_sha256"] == FORMAL_DATA_SHA256 for row in matrix["E1_cases"])


def test_r6b_e2_sensitivities_are_exact_ofat_levels():
    config, matrix = _load(CONFIG), _matrix()
    families = config["E2"]["families"]
    assert list(families) == [
        "S1_vaccine_cold_chain", "S2_crackers_retention", "S3_f_price_split",
        "S4_reliability_premium", "S5_reliability_effectiveness", "S6_shortage_severity",
    ]
    assert families["S1_vaccine_cold_chain"]["levels"] == [0.25, 0.5, 1.0]
    assert families["S2_crackers_retention"]["levels"] == [0.8, 0.9, 1.0]
    assert families["S3_f_price_split"]["levels"] == [[0.1, 0.95], [0.2, 0.85], [0.3, 0.75]]
    assert all(math.isclose(sum(level), 1.05) for level in families["S3_f_price_split"]["levels"])
    assert families["S4_reliability_premium"]["levels"] == [0.5, 1.0, 1.5]
    assert families["S5_reliability_effectiveness"]["levels"] == [[0.0, 0.4, 0.7], [0.0, 0.5, 0.8], [0.0, 0.6, 0.9]]
    assert families["S6_shortage_severity"]["levels"] == [2.0, 4.0, 6.0]
    assert matrix["counts"]["E2_families"] == 6
    assert matrix["counts"]["E2_cells"] == 18
    assert all(row["model_kind"] == "M2" and row["budget_ratio"] == 1.0 for row in matrix["E2_cases"])


def test_r6b_e3_cells_and_f_disruption_mapping_are_exact():
    matrix = _matrix()
    assert len(matrix["E3_I1_cases"]) == len(matrix["E3_I2_cases"]) == 9
    by_gamma = {}
    for row in matrix["E3_I2_cases"]:
        by_gamma.setdefault(row["gamma_delta"], row["delta_cat1_to_cat5"])
        assert row["q_survivability_cat1_to_cat5"] == [0.9, 0.85, 0.8, 0.75, 0.7]
        assert row["no_hurricane_disruption"] == 0.0
    assert by_gamma == {
        0.5: [0.05, 0.15, 0.3, 0.5, 0.5],
        1.0: [0.1, 0.3, 0.6, 1.0, 1.0],
        1.5: [0.15, 0.45, 0.9, 1.0, 1.0],
    }


def test_r6b_loho_has_15_leakage_free_conditionally_normalized_folds():
    matrix = _matrix()
    folds = matrix["E4_A_folds"]
    assert len(folds) == 15
    assert {row["held_out_hurricane"] for row in folds} == {f"h{number:02d}" for number in range(1, 16)}
    formal = _load(FORMAL_DATA)
    by_id = {row["scenario_id"]: row for row in formal["scenarios"]}
    for fold in folds:
        held = fold["held_out_hurricane"]
        train_ids = {row["scenario_id"] for row in fold["training"]}
        test_ids = {row["scenario_id"] for row in fold["test"]}
        assert train_ids.isdisjoint(test_ids)
        assert all(held not in by_id[value]["hurricanes"] for value in train_ids)
        assert all(held in by_id[value]["hurricanes"] for value in test_ids)
        assert "omega_51" in train_ids and "omega_51" not in test_ids
        assert math.isclose(sum(row["probability"] for row in fold["training"]), 1.0, abs_tol=1e-12)
        assert math.isclose(sum(row["probability"] for row in fold["test"]), 1.0, abs_tol=1e-12)


class _FakeNormal:
    def __init__(self):
        self.values = iter((-1.0, 3.1, -0.95))

    def normal(self, mean, standard_deviation):
        assert (mean, standard_deviation) == (0.0, 0.1)
        return next(self.values)


def test_r6b_truncated_normal_uses_rejection_not_clipping():
    settings = _load(CONFIG)["E4"]["synthetic"]["demand_perturbation"]
    assert _draw_truncated_normal(_FakeNormal(), settings) == -0.95


def test_r6b_synthetic_generator_is_joint_deterministic_and_shared():
    config, formal = _load(CONFIG), _load(FORMAL_DATA)
    synthetic = config["E4"]["synthetic"]
    assert synthetic["seeds"] == list(range(61001, 61011))
    assert synthetic["realizations_per_seed"] == 2000
    first = generate_synthetic_oos(formal, synthetic, 61001)
    repeated = generate_synthetic_oos(formal, synthetic, 61001)
    other = generate_synthetic_oos(formal, synthetic, 61002)
    assert first == repeated
    assert first["dataset_sha256"] != other["dataset_sha256"]
    assert len(first["rows"]) == 2000
    base = {row["scenario_id"]: row for row in formal["scenarios"]}
    observed = {row["base_scenario_id"] for row in first["rows"]}
    assert len(observed) < 2000  # sampling with replacement
    assert "omega_51" in observed  # no-hurricane is in the categorical population
    for row in first["rows"]:
        source = base[row["base_scenario_id"]]
        assert -0.95 <= row["z"] <= 3.0
        assert 0.05 <= row["shared_demand_multiplier"] <= 4.0
        assert row["q_availability"] == source["q_availability"]
        assert row["disruption"] == source["disruption"]
        if source["scenario_type"] == "no_hurricane":
            assert set(row["demand"].values()) == {0.0}
            assert (row["q_availability"], row["disruption"]) == (1.0, 0.0)
        else:
            ratios = [row["demand"][item] / source["formal_demand"][item] for item in formal["qfr_data"]["items"]]
            assert all(math.isclose(value, row["shared_demand_multiplier"], rel_tol=1e-12) for value in ratios)


def test_r6b_synthetic_registry_and_bootstrap_settings_are_frozen():
    config, matrix = _load(CONFIG), _matrix()
    registry = matrix["E4_B_dataset_registry"]
    assert len(registry) == 10
    assert {row["seed"] for row in registry} == set(range(61001, 61011))
    assert len({row["dataset_sha256"] for row in registry}) == 10
    assert all(row["realizations"] == 2000 and row["shared_by_models"] == ["M0", "M1", "M2"] for row in registry)
    statistics = config["E4"]["statistics"]
    assert statistics["bootstrap_resamples"] == 10_000
    assert statistics["bootstrap_seed"] == 62001
    assert statistics["historical_replication_unit"] == "15_LOHO_FOLDS"
    assert statistics["synthetic_replication_unit"] == "10_INDEPENDENT_SEEDS_NOT_20000_REALIZATIONS"


def test_r6b_e5_is_e1_algorithms_with_memory_only_ablation():
    config, matrix = _load(CONFIG), _matrix()
    assert config["E5"]["algorithms"] == ["A0", "A1_no_memory", "A1_full"]
    assert config["E5"]["timing_repetitions"] == 3
    assert len(matrix["E5_cases"]) == 27
    no_memory = a1_settings(memory_phase_enabled=False)
    full = a1_settings(memory_phase_enabled=True)
    differences = {key for key in no_memory if no_memory[key] != full[key]}
    assert differences == {"structure", "memory_phase_enabled"}
    assert no_memory["structure"] == "CANDIDATE_FULL_EXACT"
    assert full["structure"] == "MEMORY_CANDIDATE_FULL_EXACT"
    assert all(row["algorithm"] in {"A0", "A1_no_memory", "A1_full"} for row in matrix["E5_cases"])


def test_r6b_expanded_matrix_is_deterministic_and_matches_committed_artifact():
    matrix = _matrix()
    assert matrix == _matrix() == _load(EXPANDED)
    seal = matrix.pop("matrix_sha256")
    assert seal == canonical_json_sha256(matrix)
    assert matrix["scientific_runs"] == 0
    assert matrix["r7_started"] is False


def test_r6b_generator_module_has_no_formal_solver_entrypoint():
    source = (ROOT / "src/robust_budget_allocation/data/qfr_formal_experiments.py").read_text(encoding="utf-8")
    forbidden = ("solve_qfr_extensive_form", "solve_qfr_standard_ccg", "solve_qfr_improved_ccg", "gurobi_direct")
    assert all(value not in source for value in forbidden)
