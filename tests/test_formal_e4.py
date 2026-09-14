"""Identity and exact-evaluation checks for Formal E4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_exact_oracle import solve_exact_recourse
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import load_base_fixture, load_samples, read_csv
from robust_budget_allocation.formal.e4 import (
    BUDGET,
    E1_RESULTS,
    EXPECTED_E4B_GENERATOR,
    EXPECTED_S100,
    EXPECTED_S200,
    data_payload_for_sample,
    decision_from_e1_row,
    evaluate_oos_batch,
    generate_e4b,
    oos_payload,
    policy_sha256,
    preflight,
    rawls24_templates,
    rebind_decision,
    subset_payload,
)


ROOT = Path(__file__).resolve().parents[1]


def test_e4_preflight_reconstructs_all_frozen_identities():
    report = preflight(ROOT)
    assert report["status"] == "PASS"
    assert report["S200_sha256"] == EXPECTED_S200
    assert report["S100_sha256"] == EXPECTED_S100
    assert report["generator_sha256"] == EXPECTED_E4B_GENERATOR
    assert report["E4A_planned"] == 4800
    assert report["E4B_scenario_evaluations"] == 2_000_000
    assert report["E5_runs"] == 0


def test_e4a_subset_changes_only_training_scenario_membership():
    base, metadata = load_base_fixture(ROOT)
    sample = load_samples(ROOT)[0]
    full = data_payload_for_sample(base, metadata, sample)
    subset = subset_payload(full, [scenario for scenario in full["scenarios"] if scenario != "h09"])
    assert len(full["scenarios"]) == 24 and len(subset["scenarios"]) == 23
    assert "h09" not in subset["scenarios"]
    for field in ("budget", "q_unit_cost", "storage_cost", "retention", "flexible_capacity", "reservation_cost", "reliability_cost", "reliability_mitigation", "exercise_cost", "shortage_cost"):
        assert subset[field] == full[field]
    assert subset["budget"] == BUDGET


def test_all_s200_and_s100_frozen_e1_scientific_decisions_reconstruct_exactly():
    report = preflight(ROOT)
    base, metadata = load_base_fixture(ROOT)
    samples = {int(row["sample_index"]): row for row in load_samples(ROOT)}
    results = {int(row["sample_index"]): row for row in read_csv(ROOT / E1_RESULTS)}
    for index in report["S200_ids"]:
        data = QFRData.from_dict(data_payload_for_sample(base, metadata, samples[index]))
        decision = decision_from_e1_row(data, results[index])
        repeated = decision_from_e1_row(data, results[index])
        assert policy_sha256(decision) == policy_sha256(repeated)
        assert sum(decision.q.values()) >= 0
    assert set(report["S100_ids"]) < set(report["S200_ids"])


def test_e4b_generator_tables_are_shared_deterministic_and_frozen():
    report = preflight(ROOT)
    templates = rawls24_templates(ROOT)
    for seed in report["seeds"]:
        first = generate_e4b(seed, templates)
        second = generate_e4b(seed, templates)
        assert first == second and len(first) == 2000
        assert {row["template_id"] for row in first} <= {f"h{i:02d}" for i in range(1, 25)}
        assert all("no_hurricane" not in row for row in first)


@pytest.mark.gurobi
def test_separable_batch_matches_production_exact_recourse_objectives():
    base, metadata = load_base_fixture(ROOT)
    sample = load_samples(ROOT)[0]
    e1 = read_csv(ROOT / E1_RESULTS)[0]
    full = QFRData.from_dict(data_payload_for_sample(base, metadata, sample))
    decision = decision_from_e1_row(full, e1)
    scenarios = generate_e4b(20260904, rawls24_templates(ROOT), count=3)
    oos = QFRData.from_dict(oos_payload(base, sample, scenarios))
    rebound = rebind_decision(decision, oos)
    batch = evaluate_oos_batch(oos, rebound)
    assert batch["status"] == "optimal" and len(batch["results"]) == 3
    for row in batch["results"]:
        exact = solve_exact_recourse(oos, rebound, row["scenario_id"])
        assert exact["solver"]["status"] == "optimal"
        assert abs(float(row["recourse_loss"]) - float(exact["loss"])) <= 1e-5
        assert row["maximum_feasibility_violation"] <= 1e-5


def test_batch_witness_gate_is_not_a_scientific_result(monkeypatch):
    from robust_budget_allocation.formal import e4

    base, metadata = load_base_fixture(ROOT)
    sample = load_samples(ROOT)[0]
    e1 = read_csv(ROOT / E1_RESULTS)[0]
    full = QFRData.from_dict(data_payload_for_sample(base, metadata, sample))
    decision = decision_from_e1_row(full, e1)
    scenarios = generate_e4b(20260904, rawls24_templates(ROOT), count=1)
    oos = QFRData.from_dict(oos_payload(base, sample, scenarios))
    rebound = rebind_decision(decision, oos)
    assert e4._batch_witness_feasible(oos, rebound) is True


def test_e4_design_artifact_declares_no_reselection_or_e5():
    pre = json.loads((ROOT / "formal_results/e4_final/preflight.json").read_text(encoding="utf-8"))
    assert pre["S200_sha256"] == EXPECTED_S200
    assert pre["S100_sha256"] == EXPECTED_S100
    assert pre["generator_sha256"] == EXPECTED_E4B_GENERATOR
    assert pre["scientific_optimizations_completed"] == 0
    assert pre["E5_runs"] == 0


def test_final_e4_artifact_populations_and_recovery_audit_are_complete():
    e4a = ROOT / "formal_results/e4_final/e4a"
    e4b = ROOT / "formal_results/e4_final/e4b"
    assert len(read_csv(e4a / "scientific_results.csv")) == 4800
    assert len(read_csv(e4a / "heldout_results.csv")) == 4800
    assert len(read_csv(e4a / "policy_transition.csv")) == 4800
    assert len(read_csv(e4b / "policy_summary.csv")) == 100
    seeds = read_csv(e4b / "policy_seed_summary.csv")
    assert len(seeds) == 1000
    assert all(row["status"] == "optimal" for row in seeds)
    recovery = read_csv(e4b / "initial_failure_resolution_audit.csv")
    assert len(recovery) == 60
    assert len({row["simulation_id"] for row in recovery}) == 6
    assert all(row["production_termination"] == "infeasible" for row in recovery)
    assert all(row["scaled_retry_status"] == "optimal" for row in recovery)
    assert all(row["mapped_back_original_semantic_validation"] == "PASS" for row in recovery)
    for seed in range(20260904, 20260914):
        assert len(read_csv(e4b / "scenario_tables" / f"seed_{seed}.csv")) == 2000


def test_final_e4_manifests_preserve_frozen_guardrails():
    root_manifest = json.loads((ROOT / "formal_results/e4_final/manifest.json").read_text(encoding="utf-8"))
    assert root_manifest["failures"] == 0
    assert root_manifest["E4A_training_certified"] == 4800
    assert root_manifest["E4B_scenario_evaluations"] == 2_000_000
    assert root_manifest["model_changed"] is False
    assert root_manifest["tolerance_changed"] is False
    assert root_manifest["resampled"] is False
    assert root_manifest["S200_reselected"] is False
    assert root_manifest["S100_reselected"] is False
    assert root_manifest["generator_changed"] is False
    assert root_manifest["memory"] is False
    assert root_manifest["E5_runs"] == 0
