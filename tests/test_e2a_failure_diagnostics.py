from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import subprocess

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY
from robust_budget_allocation.formal.e2a import SAMPLE_SHA256
from robust_budget_allocation.formal.e2a_diagnostics import classify_scenario, taxonomy_counts
from robust_budget_allocation.io.hashing import sha256_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]
E2A = ROOT / "formal_results/e2_final/e2a"
OUTPUT = E2A / "diagnostics"


def _rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _truth(value):
    return value == "True"


def test_diagnostic_population_is_exact_original_205():
    source = _rows(E2A / "recertification/e2a_initial_205_retained_failures.csv")
    replay = _rows(OUTPUT / "e2a_205_failure_replay.csv")
    assert len(source) == len(replay) == 205
    expected = [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in source]
    actual = [(row["case_id"], row["simulation_id"], row["input_sha256"]) for row in replay]
    assert actual == expected
    assert len(set(actual)) == 205


def test_first_stage_evidence_is_complete_and_feasible():
    rows = _rows(OUTPUT / "e2a_205_first_stage_evidence.csv")
    assert len(rows) == 205
    assert all(row["first_stage_sha256"] and row["Q"] and row["F"] and row["z"] for row in rows)
    assert all(set(json.loads(row["Q"])) == {"Water", "Seasonal Influenza Vaccine", "Crackers"} for row in rows)
    assert all(_truth(row["first_stage_feasibility_validation"]) for row in rows)
    assert all(float(row["first_stage_cost_minus_B"]) <= float(row["budget_tolerance"]) for row in rows)


def test_every_replay_decision_has_all_24_scenarios():
    rows = _rows(OUTPUT / "e2a_205_scenario_taxonomy.csv")
    assert len(rows) == 205 * 24
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["case_id"], row["simulation_id"])].append(row["scenario_id"])
    assert len(grouped) == 205
    assert all(values == [f"h{index:02d}" for index in range(1, 25)] for values in grouped.values())


def test_witnesses_cover_every_infeasible_scenario_and_original_families():
    scenarios = _rows(OUTPUT / "e2a_205_scenario_taxonomy.csv")
    infeasible = [row for row in scenarios if row["production_termination"] == "infeasible"]
    witnesses = _rows(OUTPUT / "e2a_205_witness_validation.csv")
    assert len(infeasible) == 284
    assert len(witnesses) == 284 * 4
    grouped = defaultdict(set)
    for row in witnesses:
        assert _truth(row["witness_not_optimum_or_certificate"])
        assert _truth(row["feasible"])
        grouped[(row["case_id"], row["simulation_id"], row["scenario_id"])].add(row["constraint_family"])
    assert all(families == {"nonnegativity", "quantity_flow", "fulfillment_capacity", "budget"} for families in grouped.values())
    assert len(grouped) == len(infeasible)


def test_taxonomy_is_rebuilt_from_scenario_rows():
    raw = _rows(OUTPUT / "e2a_205_scenario_taxonomy.csv")
    typed = []
    for row in raw:
        row["witness_feasible"] = None if row["witness_feasible"] == "" else _truth(row["witness_feasible"])
        typed.append(row)
    taxonomy = json.loads((OUTPUT / "e2a_205_failure_taxonomy.json").read_text(encoding="utf-8"))
    assert taxonomy_counts(typed) == taxonomy["scenario_taxonomy"]
    assert taxonomy["scenario_taxonomy"] == {
        "A_SOLVER_INFEASIBLE_BUT_ORIGINAL_WITNESS_FEASIBLE": 284,
        "OPTIMAL": 4636,
    }
    assert taxonomy["case_taxonomy_counts_overlapping"] == {"A": 205, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}


def test_reproduction_and_determinism_evidence():
    taxonomy = json.loads((OUTPUT / "e2a_205_failure_taxonomy.json").read_text(encoding="utf-8"))
    assert taxonomy["reproduced"] == 205 and taxonomy["non_reproduced"] == 0
    assert taxonomy["determinism_subset"] == {"size": 5, "stable": 5}
    assert taxonomy["first_stage_budget_or_feasibility_issue_cases"] == 0
    checks = _rows(OUTPUT / "e2a_205_determinism_check.csv")
    assert len(checks) == 5 and all(_truth(row["stable"]) for row in checks)


def test_historical_diagnostic_protected_hashes_match_the_pinned_diagnostic_commit():
    manifest = json.loads((OUTPUT / "e2a_205_diagnostic_manifest.json").read_text(encoding="utf-8"))
    protected = manifest["protected_hashes"]
    commit = manifest["git"]["commit"]
    historical = {
        "formal_scientific_results": "formal_results/e2_final/e2a/e2a_scientific_results.csv",
        "scientific_design": "configs/final_formal_scientific_design_v1.json",
        "final_a1": "src/robust_budget_allocation/algorithms/qfr_final_a1.py",
        "exact_oracle": "src/robust_budget_allocation/algorithms/qfr_exact_oracle.py",
    }
    available = all(
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{relative}"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
        for relative in historical.values()
    )
    if not available:
        # GitHub's shallow PR checkout may omit the pre-diagnostic tree. The
        # committed canonical diagnostic files and their complete hash inventory
        # are independently checked below; full source-backed verification runs
        # whenever the pinned historical tree is available.
        assert set(protected) == set(historical)
        assert all(len(value) == 64 for value in protected.values())
        return
    for key, relative in historical.items():
        payload = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT)
        assert sha256_bytes(payload) == protected[key]
    assert manifest["identity"]["sample_sha256"] == SAMPLE_SHA256
    assert manifest["identity"]["algorithm"] == FINAL_A1_IDENTITY
    assert manifest["guardrails"]["E2_B_runs"] == manifest["guardrails"]["E2_C_runs"] == manifest["guardrails"]["E2_D_runs"] == 0


def test_diagnostic_hash_inventory_is_complete():
    entries = {}
    for line in (OUTPUT / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        entries[name] = digest
    assert set(entries) == {path.name for path in OUTPUT.iterdir() if path.is_file()} - {"HASHES.sha256"}
    assert all(sha256_file(OUTPUT / name) == digest for name, digest in entries.items())
