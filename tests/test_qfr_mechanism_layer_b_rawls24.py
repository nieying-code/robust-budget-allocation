from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qfr_mechanism_layer_a import _compact_fixed_item_value  # noqa: E402
from robust_budget_allocation.io.hashing import sha256_bytes, sha256_file  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    generate_samples,
    load_config,
    load_rawls24_heterogeneous_fixture,
    samples_csv_bytes,
)


CONFIG_PATH = ROOT / "configs/qfr_mechanism_layer_b_rawls24_v1.json"
LAYER_A = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_n1000_post_numerical_fix"
EXPECTED_SAMPLE_SHA256 = "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG_PATH)


def test_layer_b_reuses_exact_layer_a_n1000_draw_table(config):
    rows = generate_samples(config)
    payload = samples_csv_bytes(rows)
    assert len(rows) == 1000
    assert sha256_bytes(payload) == EXPECTED_SAMPLE_SHA256
    assert payload == (LAYER_A / "samples.csv").read_bytes()


def test_layer_a_pairing_source_hashes_are_frozen(config):
    pairing = config["layer_a_pairing"]
    expected = {
        "samples.csv": pairing["samples_sha256"],
        "scientific_results.csv": pairing["scientific_results_sha256"],
        "a1_computational_diagnostics.csv": pairing["a1_diagnostics_sha256"],
        "summary.json": pairing["summary_sha256"],
        "simulation_manifest.json": pairing["manifest_sha256"],
    }
    assert all(sha256_file(LAYER_A / name) == digest for name, digest in expected.items())


def test_heterogeneous_fixture_restores_only_frozen_h_and_a(config):
    payload, fixture = load_rawls24_heterogeneous_fixture(ROOT, config)
    assert payload["storage_cost"] == {
        "Water": 0.0,
        "Seasonal Influenza Vaccine": 0.0833333333333333,
        "Crackers": 0.0,
    }
    assert payload["retention"] == {
        "Water": 1.0,
        "Seasonal Influenza Vaccine": 1.0,
        "Crackers": 0.9,
    }
    assert payload["tau"] == 6.0
    assert fixture["heterogeneity_source"]["vaccine_six_month_cold_chain_cost"] == pytest.approx(0.5)
    assert fixture["heterogeneity_source"]["crackers_retention"] == 0.9
    assert fixture["scenario_count"] == 24
    assert fixture["scenario_order"] == [f"h{index:02d}" for index in range(1, 25)]


def test_layer_b_budget_is_existing_formula_applied_mechanically(config):
    payload, fixture = load_rawls24_heterogeneous_fixture(ROOT, config)
    expected = sum(
        (payload["q_unit_cost"][item] + payload["storage_cost"][item] * payload["tau"])
        * fixture["reference_demand"][item]
        / payload["retention"][item]
        for item in payload["items"]
    )
    assert fixture["B_ref_formula"] == "sum_i((cQ_i+h_i*tau)*Dref_i/a_i)"
    assert fixture["budget"] == pytest.approx(expected, abs=1e-9)
    assert fixture["budget"] == pytest.approx(19137905.85543848, abs=1e-8)


def test_conflicting_formal_matrix_identity_is_rejected(config, tmp_path):
    invalid = deepcopy(config)
    bogus = tmp_path / "matrix.json"
    bogus.write_text(json.dumps({"baseline": {"vaccine_six_month_cold_chain_cost": 0.6, "crackers_retention": 0.9}}), encoding="utf-8")
    invalid["heterogeneity"]["formal_matrix"] = {
        "path": bogus.relative_to(ROOT).as_posix() if bogus.is_relative_to(ROOT) else str(bogus),
        "sha256": sha256_file(bogus),
    }
    with pytest.raises((OSError, ValueError)):
        load_rawls24_heterogeneous_fixture(ROOT, invalid)


def test_fixed_item_serialization_remains_scalar_when_homogeneous_and_explicit_when_heterogeneous():
    assert _compact_fixed_item_value({"Water": 0.0, "Seasonal Influenza Vaccine": 0.0, "Crackers": 0.0}) == 0.0
    value = _compact_fixed_item_value({"Water": 1.0, "Seasonal Influenza Vaccine": 1.0, "Crackers": 0.9})
    assert json.loads(value) == {"Water": 1.0, "Seasonal Influenza Vaccine": 1.0, "Crackers": 0.9}
