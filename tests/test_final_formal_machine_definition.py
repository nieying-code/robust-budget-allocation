import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from robust_budget_allocation.formal.final_design import (
    E4_GENERATOR_IDENTITY, E5B_GENERATOR_IDENTITY, E5C_GENERATOR_IDENTITY,
    canonical_sha256, generate_e4b, generate_e5b, generate_e5c_items,
    select_f_supply_risk, select_reliability_economics, select_space_filling,
)
from scripts.audit_pr27_final_e1_identity import _reconstruct_samples


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads((ROOT / "docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json").read_text(encoding="utf-8"))
PR27_AUDIT = json.loads((ROOT / "docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parameter_rows():
    data = _reconstruct_samples(CONFIG["E1"])
    assert hashlib.sha256(data).hexdigest() == CONFIG["E1"]["sample_table_sha256"]
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


@pytest.fixture(scope="module")
def result_rows():
    active = set(PR27_AUDIT["f_active_filter_evidence"]["row_ids"])
    return [{"sample_index": index,
             "F_Water": 1.0 if index in active else 0.0,
             "F_Seasonal Influenza Vaccine": 0.0,
             "F_Crackers": 0.0} for index in range(1, 1001)]


@pytest.fixture(scope="module")
def templates():
    rows = list(csv.DictReader((ROOT / "data/r6_rawls24/unified_rawls_demand.csv").open(encoding="utf-8", newline="")))
    return [{
        "scenario_id": row["scenario_id"], "category": int(row["category"]),
        "demand": {"Water": float(row["water_unified"]),
                   "Seasonal Influenza Vaccine": float(row["medical_unified"]) * 10.0603621730382,
                   "Crackers": float(row["food_unified"]) * 14.0},
    } for row in rows]


def test_actual_s200_and_nested_s100_are_reproducible(parameter_rows):
    bounds = CONFIG["E1"]["bounds"]
    first = select_space_filling(parameter_rows, bounds, 200)
    second = select_space_filling(parameter_rows, bounds, 200)
    assert first == second == EVIDENCE["S_200"]["row_ids_in_selection_order"]
    assert len(first) == len(set(first)) == 200
    by_id = {int(row["sample_index"]): row for row in parameter_rows}
    s100 = select_space_filling([by_id[index] for index in first], bounds, 100)
    assert s100 == EVIDENCE["S_100"]["row_ids_in_selection_order"]
    assert len(s100) == len(set(s100)) == 100
    assert set(s100) < set(first)


def test_selector_rejects_outcome_contamination(parameter_rows):
    contaminated = [dict(row) for row in parameter_rows[:3]]
    contaminated[0]["objective_T_COST"] = "1"
    with pytest.raises(ValueError, match="outcome fields are forbidden"):
        select_space_filling(contaminated, CONFIG["E1"]["bounds"], 2)


def test_e3b_actual_representatives_are_deterministic_distinct_and_label_free(parameter_rows, result_rows):
    supply = select_f_supply_risk(parameter_rows)
    assert supply["levels"] == EVIDENCE["E3B_F_supply_risk"]["levels"]
    stripped_f = [{"sample_index": row["sample_index"],
                   "F_Water": row["F_Water"],
                   "F_Seasonal Influenza Vaccine": row["F_Seasonal Influenza Vaccine"],
                   "F_Crackers": row["F_Crackers"]} for row in result_rows]
    reliability = select_reliability_economics(parameter_rows, stripped_f, CONFIG["E1"]["policy_tolerance"])
    assert reliability["levels"] == EVIDENCE["E3B_reliability_economics"]["levels"]
    assert len(set(reliability["levels"].values())) == 3
    assert reliability["active_row_count"] == 792


def test_e4b_determinism_shape_templates_and_generator_separation(templates):
    first = generate_e4b(20260904, templates)
    again = generate_e4b(20260904, templates)
    other = generate_e4b(20260905, templates)
    assert canonical_sha256(first) == canonical_sha256(again)
    assert canonical_sha256(first) != canonical_sha256(other)
    assert len(first) == 2000
    assert {row["template_id"] for row in first} <= {f"h{i:02d}" for i in range(1, 25)}
    assert all(row["category"] in range(1, 6) for row in first)
    assert all("no_hurricane" not in row for row in first)
    assert CONFIG["E4"]["B"]["shared_scenarios_across_policies"] is True
    assert len({E4_GENERATOR_IDENTITY, E5B_GENERATOR_IDENTITY, E5C_GENERATOR_IDENTITY}) == 3


def test_e5b_prefix_nesting_common_parameter_row_and_budget_identity(templates):
    replicate = generate_e5b(20261001, templates)
    master = replicate["master_500"]
    assert len(master) == 500
    for small, large in ((50, 100), (100, 200), (200, 500)):
        assert master[:small] == master[:large][:small]
    frozen = EVIDENCE["E5B"]["replicates"][0]
    assert replicate["parameter_row_id"] == frozen["parameter_row_id"]
    assert canonical_sha256(master) == frozen["master_500_sha256"]
    assert len(set(frozen["B_r_bench_sha256"] for _ in (50, 100, 200, 500))) == 1


def test_e5c_item_nesting_ratio_common_parameter_row_and_rng_reproducibility():
    first = generate_e5c_items(20261101)
    again = generate_e5c_items(20261101)
    assert first == again
    master = first["master_9"]
    assert [row["item_id"] for row in master] == CONFIG["E5"]["C"]["item_order"]
    for size, expected in ((3, 1), (6, 2), (9, 3)):
        prefix = master[:size]
        assert {kind: sum(row["archetype"] == kind for row in prefix) for kind in ("Standard", "Preservation", "StorageLoss")} == {kind: expected for kind in ("Standard", "Preservation", "StorageLoss")}
    assert first["parameter_row_id"] == EVIDENCE["E5C"]["replicates"][0]["parameter_row_id"]


def test_final_protocol_has_no_formal_memory_metric_and_sample_sha_is_unchanged():
    protocol = (ROOT / "docs/FINAL_FORMAL_SCIENTIFIC_DESIGN_v1.md").read_text(encoding="utf-8")
    assert CONFIG["algorithm"]["memory_metrics_formal"] is False
    assert CONFIG["E5"]["memory_metrics_formal"] is False
    assert "Memory metrics are prohibited" in protocol
    assert EVIDENCE["source_sample_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert EVIDENCE["scientific_optimization_runs"] == 0
