import csv
import json
from pathlib import Path

import pytest

from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import sha256_bytes, sha256_file
from robust_budget_allocation.simulation.layer_a import (
    ITEMS,
    generate_samples,
    load_config,
    load_rawls24_neutral_fixture,
    samples_csv_bytes,
    validate_samples,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/qfr_mechanism_layer_a_rawls24_v1.json"
OLD_SAMPLES = ROOT / "simulation_results/qfr_mechanism_layer_a_n1000/samples.csv"
EXPECTED_SAMPLE_SHA = "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"


@pytest.fixture(scope="module")
def rawls24():
    config = load_config(CONFIG)
    payload, fixture = load_rawls24_neutral_fixture(ROOT, config)
    return config, QFRData.from_dict(payload), fixture


def test_rawls24_uses_exact_old_layer_a_samples(rawls24):
    config, _, _ = rawls24
    rows = generate_samples(config)
    assert validate_samples(rows, config)["status"] == "PASS"
    generated = samples_csv_bytes(rows)
    assert sha256_bytes(generated) == EXPECTED_SAMPLE_SHA
    assert generated == OLD_SAMPLES.read_bytes()


def test_rawls24_exact_single_hurricane_identity(rawls24):
    _, data, fixture = rawls24
    assert data.scenarios == tuple(f"h{index:02d}" for index in range(1, 25))
    assert fixture["scenario_count"] == 24
    assert all(row["scenario_type"] == "single_hurricane" for row in fixture["metadata"].values())
    assert {row["hurricane_name"] for row in fixture["metadata"].values()} == {
        "Alicia", "Camille", "Bonnie", "Floyd", "Andrew", "Opal", "Isabel", "Lili",
        "Katrina", "Bertha", "Fran", "Dennis", "Emily", "Georges", "Hugo", "Ike",
        "Rita", "Wilma", "Irma", "Charley", "Frances", "Ivan", "Jeanne", "Elena",
    }


def test_rawls24_reference_weights_and_budget(rawls24):
    _, data, fixture = rawls24
    assert fixture["reference_weight_sum"] == pytest.approx(1.0, abs=1e-15)
    assert fixture["florida_mass"] == pytest.approx(0.4, abs=1e-15)
    assert fixture["major_mass"] == pytest.approx(0.4444444444, abs=1e-15)
    for item in ITEMS:
        expected_dref = sum(
            fixture["reference_weights"][scenario] * data.demand[scenario][item]
            for scenario in data.scenarios
        )
        assert fixture["reference_demand"][item] == pytest.approx(expected_dref)
    expected_budget = sum(data.q_unit_cost[item] * fixture["reference_demand"][item] for item in ITEMS)
    assert data.budget == pytest.approx(expected_budget)
    assert data.budget == pytest.approx(18146405.511449322)


def test_rawls24_mapping_capacity_and_neutral_controls(rawls24):
    _, data, fixture = rawls24
    with (ROOT / "data/r6_rawls24/unified_rawls_demand.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        source = {row["scenario_id"]: row for row in csv.DictReader(handle)}
    for scenario in data.scenarios:
        assert data.demand[scenario]["Water"] == float(source[scenario]["water_unified"])
        assert data.demand[scenario]["Seasonal Influenza Vaccine"] == pytest.approx(
            float(source[scenario]["medical_unified"]) * 10.0603621730382
        )
        assert data.demand[scenario]["Crackers"] == float(source[scenario]["food_unified"]) * 14
    assert data.flexible_capacity == {
        item: max(data.demand[scenario][item] for scenario in data.scenarios) for item in ITEMS
    }
    assert data.storage_cost == dict.fromkeys(ITEMS, 0.0)
    assert data.retention == dict.fromkeys(ITEMS, 1.0)
    assert data.shortage_cost == {
        item: pytest.approx(4 * data.q_unit_cost[item]) for item in ITEMS
    }
    assert fixture["canonical_data_sha256"] == "51d2b286997556a338acf5dd28df4409d67e46bec52a02f737af4ab0ac0c5afb"


def test_old_layer_a_source_chain_remains_51_scenario_baseline():
    old_config = json.loads((ROOT / "configs/qfr_mechanism_layer_a_v1.json").read_text(encoding="utf-8"))
    old_manifest = json.loads((ROOT / "simulation_results/qfr_mechanism_layer_a_n1000/pre_run_manifest.json").read_text(encoding="utf-8"))
    assert old_config["source"]["formal_ready_path"] == "configs/r6c_formal_ready_data_v2.json"
    assert old_manifest["fixture"]["scenario_count"] == 51
    assert sha256_file(ROOT / old_config["source"]["formal_ready_path"]) == old_config["source"]["formal_ready_file_sha256"]
