from copy import deepcopy
import math
from pathlib import Path

import pytest

from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.simulation.layer_a import (
    ITEMS, PARAMETERS, classify_policy, data_for_sample, generate_samples,
    load_config, load_neutral_fixture, validate_config,
    validate_output_traceability, validate_samples,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/qfr_mechanism_layer_a_v1.json"


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def samples(config):
    return generate_samples(config)


def test_exact_n1000_unique_ids_vectors_and_finite_values(config, samples):
    report = validate_samples(samples, config)
    assert report["status"] == "PASS"
    assert len(samples) == 1000
    assert len({row["simulation_id"] for row in samples}) == 1000
    assert len({tuple(row[name] for name in PARAMETERS) for row in samples}) == 1000
    assert all(math.isfinite(row[name]) for row in samples for name in PARAMETERS)


def test_all_bounds_monotonicity_ordering_and_minimum_gaps(config, samples):
    bounds = config["bounds"]
    for row in samples:
        assert all(bounds[name][0] <= row[name] <= bounds[name][1] for name in PARAMETERS)
        assert all(row[f"rho_Q{i}"] >= row[f"rho_Q{i+1}"] for i in range(1, 5))
        assert all(row[f"rho_F{i}"] >= row[f"rho_F{i+1}"] for i in range(1, 5))
        assert row["eta_2"] > row["eta_1"] and row["eta_2"] - row["eta_1"] >= 0.05 - 1e-14
        assert row["c_R2_ratio"] > row["c_R1_ratio"] and row["c_R2_ratio"] - row["c_R1_ratio"] >= 0.05 - 1e-14


def test_every_scalar_marginal_has_exact_lhs_coverage(config, samples):
    n = len(samples)
    for name, (low, high) in config["bounds"].items():
        strata = {min(n - 1, int((row[name] - low) / (high - low) * n)) for row in samples}
        assert len(strata) == n
        assert min(row[name] for row in samples) < low + (high - low) / n
        assert max(row[name] for row in samples) > high - (high - low) / n


def test_same_seed_exact_reproduction_and_different_seed_changes_table(config, samples):
    assert generate_samples(config) == samples
    changed = deepcopy(config)
    changed["seed"] += 1
    assert generate_samples(changed) != samples


@pytest.mark.parametrize("mutation", ["count", "missing_bound", "bad_model", "bad_tolerance"])
def test_invalid_config_rejected(config, mutation):
    invalid = deepcopy(config)
    if mutation == "count":
        invalid["sample_size"] = 999
    elif mutation == "missing_bound":
        invalid["bounds"].pop("phi")
    elif mutation == "bad_model":
        invalid["model_kind"] = "M1"
    else:
        invalid["policy_tolerance"] = 0
    with pytest.raises(ValueError):
        validate_config(invalid)


def test_input_identity_hashes_are_bound_to_each_draw(samples):
    for row in samples:
        bare = {key: value for key, value in row.items() if key != "input_sha256"}
        assert row["input_sha256"] == canonical_json_sha256(bare)


def test_neutral_fixture_and_draw_adapter_preserve_schema_and_fixed_environment(config, samples):
    neutral, fixture = load_neutral_fixture(ROOT, config)
    data = data_for_sample(neutral, fixture["metadata"], samples[0])
    assert len(data.scenarios) == 51
    assert data.budget == config["fixed_environment"]["budget"]
    assert set(data.storage_cost.values()) == {0.0}
    assert set(data.retention.values()) == {1.0}
    assert fixture["formal_data_sha256"] == config["source"]["formal_data_sha256"]
    assert data.reliability_mitigation["Water"][0] == 0.0


def _first(q: float, levels: dict[int, float]):
    return {
        "reliability_levels": [0, 1, 2],
        "q": {item: q for item in ITEMS},
        "f": {item: {str(level): value for level, value in levels.items()} for item in ITEMS},
    }


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (_first(1.0, {0: 0.0, 1: 0.0, 2: 0.0}), "P1"),
        (_first(1.0, {0: 1.0, 1: 0.0, 2: 0.0}), "P2"),
        (_first(1.0, {0: 0.0, 1: 1.0, 2: 0.0}), "P3a"),
        (_first(1.0, {0: 0.0, 1: 0.0, 2: 1.0}), "P3b"),
        (_first(0.0, {0: 1.0, 1: 0.0, 2: 0.0}), "P4"),
        (_first(0.0, {0: 0.0, 1: 0.0, 2: 0.0}), "P5"),
    ],
)
def test_policy_classification(first, expected):
    assert classify_policy(first, 1e-7) == expected


def test_policy_classification_uses_tolerance_not_float_equality():
    assert classify_policy(_first(1e-8, {0: 1e-8, 1: 0.0, 2: 0.0}), 1e-7) == "P5"


def test_output_traceability_no_silent_drop_and_failure_retention(samples):
    subset = samples[:2]
    scientific = [
        {**subset[0], "status": "SUCCESS", "failure_type": ""},
        {**subset[1], "status": "FAILED", "failure_type": "solver_error"},
    ]
    computational = [
        {"simulation_id": subset[0]["simulation_id"]},
        {"simulation_id": subset[1]["simulation_id"]},
    ]
    validate_output_traceability(subset, scientific, computational)
    with pytest.raises(ValueError):
        validate_output_traceability(subset, scientific[:1], computational)
    broken = deepcopy(scientific)
    broken[1]["failure_type"] = ""
    with pytest.raises(ValueError):
        validate_output_traceability(subset, broken, computational)
