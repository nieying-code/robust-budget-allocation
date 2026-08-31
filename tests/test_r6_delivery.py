import json
from pathlib import Path

from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/R6_DATA_DELIVERY_MANIFEST.json"
HASHES = ROOT / "docs/R6_DATA_HASHES.sha256"
SOURCE_INVENTORY = ROOT / "docs/evidence/R6_SOURCE_INVENTORY_v1.json"
PROVENANCE = ROOT / "docs/evidence/R6_FORMAL_DATA_PROVENANCE_v1.csv"


def test_r6_delivery_manifest_stops_before_scientific_execution():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] == "R6_DATA_STAGE_READY_FOR_REVIEW"
    assert manifest["scenario_reconstruction"] == {
        "hurricanes": 15,
        "scenarios": 51,
        "single": 15,
        "combined": 35,
        "no_hurricane": 1,
        "probability_sum": 1.0,
        "rawls_yang_cross_check": "PASS",
    }
    assert set(manifest["execution_counts"].values()) == {0}
    assert manifest["stage_gates"] == {
        "r6_b_started": False,
        "r7_started": False,
        "merge_authorized": False,
    }
    assert manifest["q_survivability_revision"] == {
        "category_1_to_5": [0.9, 0.85, 0.8, 0.75, 0.7],
        "classification": "RESEARCH_DESIGN_CALIBRATION",
        "rule": "Cat1=0.90; subtract 0.05 per category; Cat5=0.70",
        "anchor": "R5 Pilot severe-state Q availability",
        "empirical_hurricane_damage_estimate": False,
        "formal_scientific_runs_before_revision": 0,
        "formal_optimization_result_driven": False,
    }
    assert manifest["open_scientific_blocks"] == []


def test_r6_hash_inventory_is_unique_and_valid():
    rows = [line.split("  ", 1) for line in HASHES.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({path for _, path in rows})
    assert len(rows) == 12
    for digest, relative in rows:
        assert len(digest) == 64 and digest == digest.lower()
        assert sha256_file(ROOT / relative) == digest


def test_r6_active_vaccine_price_provenance_is_current_without_value_change():
    inventory = json.loads(SOURCE_INVENTORY.read_text(encoding="utf-8"))
    source = next(row for row in inventory["web_sources"] if row["id"].startswith("CDC_PRICE_"))
    assert source == {
        "id": "CDC_PRICE_2026_2027",
        "title": "CDC 2026-2027 Adult Influenza Vaccine Price List",
        "url": "https://www.cdc.gov/vaccines-for-children/media/pdfs/2026/07/Adult-Influenza-Vaccine-Price-List-08-03-26.pdf",
        "selected_field": "Fluarix TIV, age 6 months and older, NDC 58160-0725-52, 10-pack single-dose syringe, CDC cost/dose USD 13.916, contract end 2027-02-28, GSK contract 75D30126D20714",
    }
    provenance = PROVENANCE.read_text(encoding="utf-8")
    assert "CDC 2026-2027 Adult Influenza Vaccine Price List" in provenance
    assert "58160-0725-52" in provenance
    assert "75D30126D20714" in provenance
    assert "CDC 2025-2026 Adult Influenza Vaccine Price List" not in provenance
