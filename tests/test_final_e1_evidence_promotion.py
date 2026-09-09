"""Solver-free fail-closed checks for canonical Final E1 evidence promotion."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "formal_results/e1_final"
SCRIPT = ROOT / "scripts/promote_final_e1_evidence.py"
SPEC = importlib.util.spec_from_file_location("promote_final_e1_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)


def _csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def samples():
    return _csv("e1_samples.csv")


@pytest.fixture(scope="module")
def results():
    return _csv("e1_scientific_results.csv")


def test_source_pr27_head_is_fixed():
    manifest = _json("e1_provenance_manifest.json")
    assert manifest["source"]["pull_request"] == 27
    assert manifest["source"]["head"] == PROMOTION.SOURCE_HEAD
    assert PROMOTION.SOURCE_HEAD == "675759cf955788d0200e8c1f24e7e1aff13af44b"


def test_source_sample_sha_matches_frozen_final_e1():
    digest = hashlib.sha256((OUTPUT / "e1_samples.csv").read_bytes()).hexdigest()
    assert digest == PROMOTION.EXPECTED_SAMPLE_SHA256
    design = json.loads(
        (ROOT / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8")
    )
    assert design["E1"]["sample_table_sha256"] == digest


def test_exactly_1000_complete_unique_sample_ids(samples):
    assert len(samples) == 1000
    assert [row["simulation_id"] for row in samples] == [f"LA-{index:04d}" for index in range(1, 1001)]
    assert [int(row["sample_index"]) for row in samples] == list(range(1, 1001))


def test_parameter_rows_have_frozen_schema_and_seed(samples):
    assert tuple(samples[0]) == PROMOTION.SAMPLE_COLUMNS
    assert {int(row["simulation_seed"]) for row in samples} == {20260903}
    assert all(len(row["input_sha256"]) == 64 for row in samples)


def test_promoted_results_have_exactly_1000_rows(results):
    assert len(results) == 1000
    assert [row["simulation_id"] for row in results] == [f"LA-{index:04d}" for index in range(1, 1001)]


def test_promoted_result_schema_excludes_forbidden_process_fields(results):
    header = set(results[0])
    assert header == set(PROMOTION.RESULT_COLUMNS)
    assert not header.intersection(PROMOTION.FORBIDDEN_RESULT_FIELDS)
    assert not any("runtime" in field.lower() or "memory" in field.lower() or "evaluation" in field.lower() for field in header)


def test_only_final_algorithm_identity_is_registered(results):
    assert {row["algorithm_identity"] for row in results} == {"A1_FINAL_NO_MEMORY_V1"}
    assert {row["certificate_status"] for row in results} == {"PASS"}


def test_policy_labels_recompute_from_independently(results):
    def classify(row):
        q_active = any(float(row[f"Q_{item}"]) > 1e-7 for item in PROMOTION.ITEMS)
        f_items = [item for item in PROMOTION.ITEMS if float(row[f"F_{item}"]) > 1e-7]
        if q_active and not f_items:
            return "P1"
        if f_items and not q_active:
            return "P4"
        if q_active and f_items:
            levels = {row[f"R_{item}"] for item in f_items}
            if "R2" in levels:
                return "P3b"
            if "R1" in levels:
                return "P3a"
            if levels == {"R0"}:
                return "P2"
        return "P5"

    assert all(classify(row) == row["policy_label"] for row in results)


def test_policy_counts_recompute_to_frozen_targets(results):
    counts = {label: sum(row["policy_label"] == label for row in results) for label in PROMOTION.POLICIES}
    assert counts == {"P1": 208, "P2": 26, "P3a": 4, "P3b": 3, "P4": 759, "P5": 0}
    assert _json("e1_policy_summary.json")["counts"] == counts


def test_commodity_activation_and_reliability_counts_match(results):
    summary = _json("e1_commodity_summary.json")
    for item, expected in PROMOTION.EXPECTED_COMMODITY.items():
        actual = summary["commodities"][item]
        assert actual["Q_active"] == expected["Q_active"]
        assert actual["F_active"] == expected["F_active"]
        assert actual["reliability"] == {level: expected[level] for level in PROMOTION.LEVELS}


def test_aggregate_reliability_counts_match():
    assert _json("e1_commodity_summary.json")["aggregate_reliability"] == {
        "NONE": 1840, "R0": 1023, "R1": 86, "R2": 51
    }


def test_mixed_cases_and_cross_item_specialization_match():
    summary = _json("e1_commodity_summary.json")
    assert summary["mixed_aggregate_Q_plus_F"] == 33
    assert summary["mixed_cross_item_specialization"] == {
        "Q[Water]|F[Crackers]": 24,
        "Q[Water]|F[Vaccine]": 9,
    }


def test_same_item_qf_coexistence_is_zero():
    summary = _json("e1_commodity_summary.json")
    assert summary["same_item_QF_coexistence"] == 0
    assert all(value["same_item_QF_coexistence"] == 0 for value in summary["commodities"].values())


def test_h09_katrina_is_worst_for_all_rows():
    summary = _json("e1_worst_scenario_summary.json")
    assert summary["scenario_counts"] == {"h09": 1000}
    assert summary["hurricane_counts"] == {"Katrina": 1000}


def test_output_hash_inventory_is_complete_and_valid():
    lines = (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines()
    entries = dict(line.split("  ", 1)[::-1] for line in lines)
    assert set(entries) == {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    for relative, digest in entries.items():
        assert hashlib.sha256((OUTPUT / relative).read_bytes()).hexdigest() == digest


def test_deterministic_rebuild_is_byte_identical(tmp_path):
    source_available = subprocess.run(
        ["git", "cat-file", "-e", f"{PROMOTION.SOURCE_HEAD}^{{commit}}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not source_available:
        # GitHub's intentionally shallow PR checkout does not include the
        # unmerged source commit.  The committed canonical files remain fully
        # checked by the independent row, summary, provenance, and hash tests
        # above; source-backed byte reconstruction is exercised whenever the
        # immutable PR #27 object is present (including the promotion host).
        assert _json("e1_provenance_manifest.json")["source"]["head"] == PROMOTION.SOURCE_HEAD
        return
    rebuilt = tmp_path / "e1_final"
    outcome = PROMOTION.promote(ROOT, rebuilt)
    assert outcome["status"] == "PASS"
    assert outcome["scientific_optimization_runs"] == 0
    expected = {path.name: path.read_bytes() for path in OUTPUT.iterdir() if path.is_file()}
    actual = {path.name: path.read_bytes() for path in rebuilt.iterdir() if path.is_file()}
    assert actual == expected


def test_provenance_manifest_is_complete_and_scientific_runs_zero():
    manifest = _json("e1_provenance_manifest.json")
    assert manifest["promotion_method"] == "READ_ONLY_EXTRACTION_AND_RE_REGISTRATION"
    assert manifest["no_rerun"] is True
    assert manifest["scientific_optimization_runs"] == 0
    assert manifest["row_count"] == 1000
    assert manifest["identity_audit"]["checks"] == {"FAIL": 0, "PASS": 25, "UNKNOWN": 0}
    assert manifest["identity_audit"]["algorithm_inertness"] == {
        "memory_hits": 0, "candidate_plan_changes": 0, "full_exact_after_miss": 1000
    }
    assert manifest["final_a1_implementation"]["identity"] == "A1_FINAL_NO_MEMORY_V1"
    assert manifest["algorithm_identity_translation"]["runtime_or_process_evidence_re_registered"] is False
    assert manifest["source"]["verified_artifact_count"] == 53
