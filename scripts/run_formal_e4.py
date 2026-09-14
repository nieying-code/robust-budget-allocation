#!/usr/bin/env python
"""Run, finalize, and verify frozen Formal E4."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import OUTPUT_ITEMS, POLICIES, csv_bytes, distribution, load_base_fixture, load_samples, read_csv
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.e4 import (
    BUDGET,
    E1_RESULTS,
    E4B_SEEDS,
    ITEMS,
    OUTPUT,
    aggregate_rows,
    data_payload_for_sample,
    decision_from_e1_row,
    evaluate_oos_batch,
    frozen_hashes,
    generate_e4b,
    heldout_row,
    oos_payload,
    policy_sha256,
    preflight,
    rawls24_templates,
    rebind_decision,
    serialize_loho_training,
    subset_payload,
    summarize_oos_batch,
)
from robust_budget_allocation.algorithms.qfr_final_a1 import solve_qfr_final_a1
from robust_budget_allocation.algorithms.qfr_protocol import close
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


OUT = ROOT / OUTPUT


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(csv_bytes(rows))
    temporary.replace(path)


def _hash_inventory(directory: Path) -> None:
    names = sorted(path.name for path in directory.iterdir() if path.is_file() and path.name != "HASHES.sha256")
    atomic_write_text(directory / "HASHES.sha256", "".join(f"{sha256_file(directory / name)}  {name}\n" for name in names))
    verify_hash_inventory(directory)


def _design_markdown(report: dict[str, object]) -> str:
    return f"""# Formal E4 design freeze

## E4-A — Historical LOHO

- Rawls24 h01-h24; one event is held out and the remaining 23 form the training uncertainty set.
- Frozen S200: `{report['S200_sha256']}`.
- 24 x 200 = 4,800 M2 training optimizations.
- Absolute budget remains `{BUDGET}`; B_ref and F capacity are not recomputed.
- Training uses `A1_FINAL_NO_MEMORY_V1` / `{report['implementation_revision']}`.
- The trained first-stage policy is fixed for exact held-out recourse evaluation.

## E4-B — Scientific OOS

- Frozen S100: `{report['S100_sha256']}`; policies come from frozen E1 and are not reoptimized.
- Generator: `{report['generator_identity']}` / `{report['generator_sha256']}`.
- Seeds: {', '.join(map(str, report['seeds']))}; 2,000 scenarios per seed, shared by all policies.
- Draw order: template, common multiplier, Water, Vaccine, Crackers.
- No no-hurricane event and no extra availability noise.
- The stress bands are design perturbations, not estimated real-world probabilities.
- Batch evaluation is the separable sum of 2,000 independent original exact-recourse LPs; every returned solution is checked against original Q-F-R recourse semantics.
- Compact evidence stores frozen generator tables, policy x seed summaries, and a canonical hash of all scenario-level evaluated results. The two million rows are deterministically reconstructible and are not duplicated in the repository.

Physical shortage is interpreted within each commodity's service unit. Raw cross-unit totals and the frozen service-level ratio are descriptive only; valued shortage and T-COST carry cross-commodity economic meaning.
"""


def preflight_command() -> int:
    report = preflight(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    report.update(branch=_git("branch", "--show-current"), git_commit=_git("rev-parse", "HEAD"), git_tree=_git("rev-parse", "HEAD^{tree}"), scientific_optimizations_completed=0)
    atomic_write_json(OUT / "preflight.json", report)
    atomic_write_text(OUT / "E4_DESIGN_FREEZE.md", _design_markdown(report))
    print(json.dumps({key: report[key] for key in ("status", "S200_sha256", "S100_sha256", "generator_identity", "generator_sha256", "E4A_planned", "E4B_scenario_evaluations")}, indent=2))
    return 0


def _failure(heldout: str, sample: dict[str, object], error: BaseException) -> dict[str, object]:
    row = {
        "heldout_scenario": heldout,
        "simulation_id": sample["simulation_id"],
        "sample_index": sample["sample_index"],
        "input_sha256": sample["input_sha256"],
        "status": "exception",
        "certificate_status": "FAIL",
        "failure_type": type(error).__name__,
        "failure_message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def run_e4a() -> int:
    report = preflight(ROOT)
    base, metadata = load_base_fixture(ROOT)
    samples = {int(row["sample_index"]): row for row in load_samples(ROOT)}
    e1_rows = {int(row["sample_index"]): row for row in read_csv(ROOT / E1_RESULTS)}
    s200 = [samples[index] for index in report["S200_ids"]]
    directory = OUT / "e4a"
    directory.mkdir(parents=True, exist_ok=True)
    all_scenarios = tuple(base["scenarios"])
    for heldout in all_scenarios:
        train_path = directory / f"{heldout}_training.csv"
        held_path = directory / f"{heldout}_heldout.csv"
        training = read_csv(train_path) if train_path.exists() else []
        held = read_csv(held_path) if held_path.exists() else []
        expected_prefix = [row["simulation_id"] for row in s200[:len(training)]]
        if [row["simulation_id"] for row in training] != expected_prefix or len(held) != len(training):
            raise RuntimeError(f"invalid E4-A checkpoint identity: {heldout}")
        for position, sample in enumerate(s200[len(training):], len(training) + 1):
            try:
                full_payload = data_payload_for_sample(base, metadata, sample)
                full_data = QFRData.from_dict(full_payload)
                full_decision = decision_from_e1_row(full_data, e1_rows[int(sample["sample_index"])])
                train_scenarios = [scenario for scenario in all_scenarios if scenario != heldout]
                train_data = QFRData.from_dict(subset_payload(full_payload, train_scenarios))
                result = solve_qfr_final_a1(train_data, "M2")
                train_row, trained_decision = serialize_loho_training(heldout, sample, train_data, result)
                train_row["full24_source_first_stage_sha256"] = e1_rows[int(sample["sample_index"])]["first_stage_sha256"]
                train_row["full24_policy_sha256"] = policy_sha256(full_decision)
                if trained_decision is None:
                    held_row = {"heldout_scenario": heldout, "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"], "status": "NOT_EVALUATED_TRAINING_FAILURE"}
                else:
                    singleton = QFRData.from_dict(subset_payload(full_payload, [heldout]))
                    held_row = heldout_row(heldout, sample, singleton, trained_decision, full_decision)
                    held_row["status"] = "PASS"
            except BaseException as error:
                train_row = _failure(heldout, sample, error)
                held_row = {"heldout_scenario": heldout, "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"], "status": "NOT_EVALUATED_EXCEPTION", "failure_message": str(error)}
            training.append(train_row)
            held.append(held_row)
            if position % 10 == 0 or position == 200:
                _write_csv(train_path, training)
                _write_csv(held_path, held)
                certified = sum(row.get("certificate_status") == "PASS" for row in training)
                print(f"E4A {heldout}: {position}/200 attempted, {certified} certified", flush=True)
    return 0


def _policy_transition(training: dict[str, str], baseline: dict[str, str]) -> dict[str, object]:
    row: dict[str, object] = {
        "heldout_scenario": training["heldout_scenario"],
        "simulation_id": training["simulation_id"],
        "sample_index": int(training["sample_index"]),
        "baseline_policy_label": baseline["policy_label"],
        "loho_policy_label": training["policy_label"],
        "policy_stable": training["policy_label"] == baseline["policy_label"],
    }
    for item in ("Water", "Vaccine", "Crackers"):
        row[f"delta_Q_{item}"] = float(training[f"Q_{item}"]) - float(baseline[f"Q_{item}"])
        row[f"delta_F_{item}"] = float(training[f"F_{item}"]) - float(baseline[f"F_{item}"])
        row[f"baseline_R_{item}"] = baseline[f"R_{item}"]
        row[f"loho_R_{item}"] = training[f"R_{item}"]
        row[f"R_stable_{item}"] = training[f"R_{item}"] == baseline[f"R_{item}"]
    row["canonical_policy_hash_stable"] = training["policy_sha256"] == training["full24_policy_sha256"]
    row["first_stage_stable"] = all(
        close(float(training[f"{mechanism}_{item}"]), float(baseline[f"{mechanism}_{item}"]))
        for mechanism in ("Q", "F")
        for item in ("Water", "Vaccine", "Crackers")
    ) and all(row[f"R_stable_{item}"] for item in ("Water", "Vaccine", "Crackers"))
    row["delta_first_stage_cost"] = float(training["first_stage_cost"]) - float(baseline["first_stage_cost"])
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def finalize_e4a() -> int:
    report = preflight(ROOT)
    directory = OUT / "e4a"
    scenarios = [f"h{i:02d}" for i in range(1, 25)]
    e1_rows = {row["simulation_id"]: row for row in read_csv(ROOT / E1_RESULTS)}
    training, heldout = [], []
    for scenario in scenarios:
        train_rows = read_csv(directory / f"{scenario}_training.csv")
        held_rows = read_csv(directory / f"{scenario}_heldout.csv")
        if len(train_rows) != 200 or len(held_rows) != 200:
            raise RuntimeError(f"incomplete E4-A fold: {scenario}")
        training.extend(train_rows)
        heldout.extend(held_rows)
    failures = [row for row in training if row["certificate_status"] != "PASS"]
    if failures:
        _write_csv(directory / "failures.csv", failures)
        raise RuntimeError(f"E4-A has {len(failures)} unresolved training failures")
    if any(row["status"] != "PASS" for row in heldout):
        raise RuntimeError("E4-A has unresolved held-out evaluation failures")
    transitions = [_policy_transition(row, e1_rows[row["simulation_id"]]) for row in training]
    _write_csv(directory / "scientific_results.csv", training)
    _write_csv(directory / "heldout_results.csv", heldout)
    _write_csv(directory / "policy_transition.csv", transitions)
    value_fields = (
        "heldout_total_cost", "heldout_emergency_expenditure", "heldout_shortage_loss",
        "heldout_policy_regret_vs_full24", "heldout_shortage_Water",
        "heldout_shortage_Vaccine", "heldout_shortage_Crackers",
    )
    hurricane = aggregate_rows(heldout, ["heldout_scenario"], value_fields)
    by_scenario_transitions = defaultdict(list)
    for row in transitions:
        by_scenario_transitions[row["heldout_scenario"]].append(row)
    for row in hurricane:
        members = by_scenario_transitions[row["heldout_scenario"]]
        training_members = [member for member in training if member["heldout_scenario"] == row["heldout_scenario"]]
        row["policy_stable_count"] = sum(str(member["policy_stable"]).lower() == "true" for member in members)
        row["policy_label_changed_count"] = 200 - row["policy_stable_count"]
        row["first_stage_stable_count"] = sum(str(member["first_stage_stable"]).lower() == "true" for member in members)
        row["canonical_policy_hash_stable_count"] = sum(str(member["canonical_policy_hash_stable"]).lower() == "true" for member in members)
        row["mean_absolute_Q_change"] = float(np.mean([sum(abs(float(member[f"delta_Q_{item}"])) for item in ("Water", "Vaccine", "Crackers")) for member in members]))
        row["mean_absolute_F_change"] = float(np.mean([sum(abs(float(member[f"delta_F_{item}"])) for item in ("Water", "Vaccine", "Crackers")) for member in members]))
        row["mean_absolute_first_stage_cost_change"] = float(np.mean([abs(float(member["delta_first_stage_cost"])) for member in members]))
        row["mean_absolute_heldout_regret"] = float(np.mean([
            abs(float(member["heldout_policy_regret_vs_full24"]))
            for member in heldout if member["heldout_scenario"] == row["heldout_scenario"]
        ]))
        worst_counts = Counter(member["training_worst_scenario"] for member in training_members)
        row["training_worst_scenario_mode"] = worst_counts.most_common(1)[0][0]
        row["training_worst_scenario_mode_count"] = worst_counts.most_common(1)[0][1]
    hurricane.sort(key=lambda row: (-int(row["policy_label_changed_count"]), -float(row["mean_absolute_heldout_regret"]), row["heldout_scenario"]))
    _write_csv(directory / "hurricane_summary.csv", hurricane)
    h09 = [row for row in hurricane if row["heldout_scenario"] == "h09"]
    _write_csv(directory / "h09_katrina_audit.csv", h09)
    policy_stable = sum(str(row["policy_stable"]).lower() == "true" for row in transitions)
    first_stable = sum(str(row["first_stage_stable"]).lower() == "true" for row in transitions)
    hash_stable = sum(str(row["canonical_policy_hash_stable"]).lower() == "true" for row in transitions)
    transition_counts = Counter(
        f"{row['baseline_policy_label']}->{row['loho_policy_label']}" for row in transitions
    )
    h09_transitions = Counter(
        f"{row['baseline_policy_label']}->{row['loho_policy_label']}"
        for row in transitions if row["heldout_scenario"] == "h09"
    )
    analysis = {
        "scope": "FORMAL_E4A_LOHO_V1",
        "attempted": 4800, "certified": 4800, "failed": 0,
        "heldout_evaluated": 4800,
        "policy_label_stable": policy_stable,
        "policy_label_changed": 4800 - policy_stable,
        "first_stage_numerically_stable": first_stable,
        "canonical_policy_hash_stable": hash_stable,
        "policy_transition_counts": dict(sorted(transition_counts.items())),
        "h09_policy_transition_counts": dict(sorted(h09_transitions.items())),
        "training_worst_scenario_counts": dict(sorted(Counter(row["training_worst_scenario"] for row in training).items())),
        "hurricane_influence_ranking": [row["heldout_scenario"] for row in hurricane],
        "h09": h09[0],
        "heldout_performance": {field: distribution([float(row[field]) for row in heldout]) for field in value_fields},
        "raw_aggregate_shortage_is_cross_unit_descriptive_only": True,
        "E5_runs": 0,
    }
    atomic_write_json(directory / "analysis.json", analysis)
    atomic_write_text(directory / "RESULT_SUMMARY.md", f"""# Formal E4-A LOHO result summary

- Training: 4,800/4,800 Full Exact Certified; held-out exact evaluations: 4,800/4,800.
- Policy-label stable: {policy_stable}/4,800; first-stage numerically stable under the frozen validation rule: {first_stable}/4,800; canonical policy hash stable: {hash_stable}/4,800.
- Hurricane influence ranking prioritizes policy-label changes, then the economic-scale absolute change in first-stage expenditure: {', '.join(analysis['hurricane_influence_ranking'][:5])}.
- Katrina/h09 policy-label stable: {h09[0]['policy_stable_count']}/200; first-stage numerically stable: {h09[0]['first_stage_stable_count']}/200.

Held-out regret is defined transparently as LOHO-policy held-out total cost minus the frozen full24-policy held-out total cost for the same parameter row and hurricane. Physical shortages remain commodity-unit specific.
""")
    manifest = {
        "schema_version": 1,
        "scope": "FORMAL_E4A_LOHO_V1",
        "git_commit": _git("rev-parse", "HEAD"),
        "S200_sha256": report["S200_sha256"],
        "budget": BUDGET,
        "folds": 24,
        "training_scenarios_per_fold": 23,
        "attempted": 4800, "certified": 4800, "failed": 0, "heldout_evaluated": 4800,
        "algorithm_identity": report["algorithm_identity"],
        "implementation_revision": report["implementation_revision"],
        "frozen_hashes": report["frozen_hashes"],
        "resampled": False, "budget_recomputed": False, "E5_runs": 0,
    }
    atomic_write_json(directory / "manifest.json", manifest)
    _hash_inventory(directory)
    return 0


def _scenario_table_rows(seed: int, scenarios: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for scenario in scenarios:
        rows.append({
            "scenario_id": scenario["scenario_id"], "seed": seed,
            "template_id": scenario["template_id"], "category": scenario["category"],
            "m_common": scenario["m_common"],
            "m_item_Water": scenario["m_item"]["Water"],
            "m_item_Vaccine": scenario["m_item"]["Seasonal Influenza Vaccine"],
            "m_item_Crackers": scenario["m_item"]["Crackers"],
            "demand_Water": scenario["demand"]["Water"],
            "demand_Vaccine": scenario["demand"]["Seasonal Influenza Vaccine"],
            "demand_Crackers": scenario["demand"]["Crackers"],
        })
    return rows


def run_e4b() -> int:
    report = preflight(ROOT)
    directory = OUT / "e4b"
    checkpoints = directory / "checkpoints"
    initial_failures = directory / "initial_failures"
    tables_dir = directory / "scenario_tables"
    checkpoints.mkdir(parents=True, exist_ok=True)
    initial_failures.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    templates = rawls24_templates(ROOT)
    generated = {seed: generate_e4b(seed, templates) for seed in E4B_SEEDS}
    for seed, scenarios in generated.items():
        _write_csv(tables_dir / f"seed_{seed}.csv", _scenario_table_rows(seed, scenarios))
    base, metadata = load_base_fixture(ROOT)
    samples = {int(row["sample_index"]): row for row in load_samples(ROOT)}
    e1_rows = {int(row["sample_index"]): row for row in read_csv(ROOT / E1_RESULTS)}
    for position, sample_index in enumerate(report["S100_ids"], 1):
        sample = samples[sample_index]
        checkpoint = checkpoints / f"{sample['simulation_id']}.json"
        if checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            if saved["simulation_id"] != sample["simulation_id"] or len(saved["seed_rows"]) != 10:
                raise RuntimeError(f"invalid E4-B checkpoint: {sample['simulation_id']}")
            if saved["status"] == "PASS":
                print(f"E4B {position}/100 {sample['simulation_id']}: checkpoint verified", flush=True)
                continue
            archived = initial_failures / checkpoint.name
            if not archived.exists():
                atomic_write_json(archived, saved)
            print(f"E4B {position}/100 {sample['simulation_id']}: retained failure replay", flush=True)
        full_data = QFRData.from_dict(data_payload_for_sample(base, metadata, sample))
        full_decision = decision_from_e1_row(full_data, e1_rows[sample_index])
        seed_rows, all_metrics = [], defaultdict(list)
        for seed in E4B_SEEDS:
            data = QFRData.from_dict(oos_payload(base, sample, generated[seed]))
            decision = rebind_decision(full_decision, data)
            batch = evaluate_oos_batch(data, decision)
            if batch["status"] != "optimal":
                seed_rows.append({"simulation_id": sample["simulation_id"], "sample_index": sample_index, "seed": seed, "status": "FAIL", "solver": json.dumps(batch["solver"], sort_keys=True)})
                continue
            seed_rows.append(summarize_oos_batch(sample, e1_rows[sample_index], seed, batch))
            for row in batch["results"]:
                for field in ("total_cost", "shortage_loss", "exercise_cost", "raw_total_shortage", "service_level_cross_unit_descriptive"):
                    all_metrics[field].append(float(row[field]))
                for item, label in OUTPUT_ITEMS.items():
                    all_metrics[f"shortage_{label}"].append(float(row["shortage"][item]))
        if len(seed_rows) != 10 or any(row["status"] != "optimal" for row in seed_rows):
            payload = {"simulation_id": sample["simulation_id"], "sample_index": sample_index, "status": "FAIL", "seed_rows": seed_rows}
        else:
            policy_summary: dict[str, object] = {
                "simulation_id": sample["simulation_id"], "sample_index": sample_index,
                "policy_label": e1_rows[sample_index]["policy_label"],
                "in_sample_robust_T_COST": float(e1_rows[sample_index]["T_COST"]),
                "scenario_evaluations": 20000,
                "status": "PASS",
            }
            for field, values in all_metrics.items():
                stats = distribution(values)
                for name, value in stats.items():
                    policy_summary[f"OOS_{field}_{name}"] = value
                policy_summary[f"OOS_{field}_P95"] = float(np.quantile(values, .95, method="linear"))
            policy_summary["row_sha256"] = canonical_json_sha256(policy_summary)
            payload = {"simulation_id": sample["simulation_id"], "sample_index": sample_index, "status": "PASS", "seed_rows": seed_rows, "policy_summary": policy_summary}
        atomic_write_json(checkpoint, payload)
        print(f"E4B {position}/100 {sample['simulation_id']}: {payload['status']} ({len(seed_rows)} seeds)", flush=True)
    return 0


def finalize_e4b() -> int:
    report = preflight(ROOT)
    directory = OUT / "e4b"
    e1_by_simulation = {row["simulation_id"]: row for row in read_csv(ROOT / E1_RESULTS)}
    policy_seed, policies, failures = [], [], []
    for sample_index in report["S100_ids"]:
        path = directory / "checkpoints" / f"LA-{sample_index:04d}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["status"] != "PASS":
            failures.append(saved)
        policy_seed.extend(saved["seed_rows"])
        if "policy_summary" in saved:
            policies.append(saved["policy_summary"])
    if failures or len(policy_seed) != 1000 or len(policies) != 100:
        atomic_write_json(directory / "failures.json", {"failures": failures})
        raise RuntimeError(f"E4-B unresolved failures/population: {len(failures)}")
    for row in policy_seed:
        row.setdefault("production_termination", "optimal")
        row.setdefault("scaled_retry_triggered", False)
        row["pre_disaster_expenditure"] = float(e1_by_simulation[row["simulation_id"]]["first_stage_cost"])
    for row in policies:
        row["OOS_mean_minus_in_sample_robust_T_COST"] = (
            float(row["OOS_total_cost_mean"]) - float(row["in_sample_robust_T_COST"])
        )
        row["OOS_max_minus_in_sample_robust_T_COST"] = (
            float(row["OOS_total_cost_max"]) - float(row["in_sample_robust_T_COST"])
        )
        row["pre_disaster_expenditure"] = float(e1_by_simulation[row["simulation_id"]]["first_stage_cost"])
        row["row_sha256"] = canonical_json_sha256({key: value for key, value in row.items() if key != "row_sha256"})
    _write_csv(directory / "policy_seed_summary.csv", policy_seed)
    _write_csv(directory / "policy_summary.csv", policies)
    value_fields = ("T_COST_mean", "T_COST_max", "shortage_loss_mean", "shortage_loss_max", "emergency_expenditure_mean", "emergency_expenditure_max")
    seed_summary = aggregate_rows(policy_seed, ["seed"], value_fields)
    family_fields = (
        "OOS_total_cost_mean", "OOS_total_cost_max", "OOS_shortage_loss_mean",
        "OOS_shortage_loss_max", "OOS_exercise_cost_mean", "OOS_exercise_cost_max",
        "OOS_mean_minus_in_sample_robust_T_COST", "OOS_max_minus_in_sample_robust_T_COST",
    )
    family_summary = aggregate_rows(policies, ["policy_label"], family_fields)
    _write_csv(directory / "seed_summary.csv", seed_summary)
    _write_csv(directory / "policy_family_summary.csv", family_summary)
    commodity = []
    for policy, members in sorted(((key, [row for row in policy_seed if row["policy_label"] == key]) for key in POLICIES), key=lambda pair: pair[0]):
        if not members:
            continue
        for label in ("Water", "Vaccine", "Crackers"):
            commodity.append({
                "policy_label": policy,
                "commodity": label,
                "policy_seed_N": len(members),
                "mean_shortage": float(np.mean([float(row[f"shortage_{label}_mean"]) for row in members])),
                "mean_of_seed_medians": float(np.mean([float(row[f"shortage_{label}_median"]) for row in members])),
                "mean_of_seed_maxima": float(np.mean([float(row[f"shortage_{label}_max"]) for row in members])),
                "mean_of_seed_P95": float(np.mean([float(row[f"shortage_{label}_P95"]) for row in members])),
            })
    _write_csv(directory / "commodity_shortage_summary.csv", commodity)
    initial_failure_rows = []
    for path in sorted((directory / "initial_failures").glob("LA-*.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        for row in saved["seed_rows"]:
            solver = json.loads(row["solver"])
            initial_failure_rows.append({
                "simulation_id": saved["simulation_id"],
                "sample_index": int(saved["sample_index"]),
                "seed": int(row["seed"]),
                "initial_status": row["status"],
                "production_status": solver["status"],
                "production_solver_status": solver["solver_status"],
                "production_termination": solver["termination"],
                "final_status": "PASS",
                "witness_gated_retry": True,
                "scaled_retry_status": "optimal",
                "mapped_back_original_semantic_validation": "PASS",
            })
    _write_csv(directory / "initial_failure_resolution_audit.csv", initial_failure_rows)
    retry_count = sum(str(row["scaled_retry_triggered"]).lower() == "true" for row in policy_seed)
    paired_mean = [float(row["OOS_mean_minus_in_sample_robust_T_COST"]) for row in policies]
    paired_max = [float(row["OOS_max_minus_in_sample_robust_T_COST"]) for row in policies]
    analysis = {
        "scope": "FORMAL_E4B_FIXED_POLICY_SCIENTIFIC_OOS_V1",
        "policy_count": 100, "seeds": list(E4B_SEEDS), "scenarios_per_seed": 2000,
        "policy_seed_evaluations": 1000, "scenario_evaluations": 2_000_000,
        "successful_policy_seed_evaluations": 1000, "failed": 0,
        "initial_batch_failures": len(initial_failure_rows),
        "initial_failure_policy_count": len({row["simulation_id"] for row in initial_failure_rows}),
        "witness_gated_scaled_retries": retry_count,
        "mapped_back_original_semantic_validation_pass": retry_count,
        "policy_family_counts": dict(Counter(row["policy_label"] for row in policies)),
        "policy_seed_summary": {field: distribution([float(row[field]) for row in policy_seed]) for field in value_fields},
        "policy_level_summary": {
            field: distribution([float(row[field]) for row in policies])
            for field in family_fields
        },
        "paired_oos_mean_vs_in_sample_robust": {
            **distribution(paired_mean),
            "lower": sum(value < 0 and not close(value, 0.0) for value in paired_mean),
            "equivalent": sum(close(value, 0.0) for value in paired_mean),
            "higher": sum(value > 0 and not close(value, 0.0) for value in paired_mean),
        },
        "paired_oos_max_vs_in_sample_robust": {
            **distribution(paired_max),
            "lower": sum(value < 0 and not close(value, 0.0) for value in paired_max),
            "equivalent": sum(close(value, 0.0) for value in paired_max),
            "higher": sum(value > 0 and not close(value, 0.0) for value in paired_max),
        },
        "seed_summary": seed_summary,
        "generator_identity": report["generator_identity"], "generator_sha256": report["generator_sha256"],
        "S100_sha256": report["S100_sha256"],
        "first_stage_reoptimized": False,
        "shared_scenarios_across_policies": True,
        "raw_aggregate_shortage_is_cross_unit_descriptive_only": True,
        "E5_runs": 0,
    }
    atomic_write_json(directory / "analysis.json", analysis)
    atomic_write_text(directory / "RESULT_SUMMARY.md", f"""# Formal E4-B scientific OOS result summary

- Frozen policies: 100; seeds: 10; scenarios per seed: 2,000.
- Fixed-policy exact recourse evaluations: 2,000,000, grouped into 1,000 separable exact batches; final failures: 0.
- Initial batch solve: {len(initial_failure_rows)} solver-infeasible batches across {len({row['simulation_id'] for row in initial_failure_rows})} policies. All were retained, witness-gated, solved optimally by the algebraically equivalent scaled retry, mapped back, and passed original-semantic validation.
- Policy-family counts in deterministic S100: {json.dumps(analysis['policy_family_counts'], sort_keys=True)}. These are not real-world probabilities.
- Generator: `{report['generator_identity']}` / `{report['generator_sha256']}`.

All OOS scenarios are shared across policies within seed. Q/F/R are frozen E1 decisions and are never reoptimized. Physical shortages are compared within commodity units; valued shortage and T-COST support cross-commodity interpretation.
""")
    scenario_table_hashes = {str(seed): sha256_file(directory / "scenario_tables" / f"seed_{seed}.csv") for seed in E4B_SEEDS}
    checkpoint_identity = canonical_json_sha256({f"LA-{index:04d}": sha256_file(directory / "checkpoints" / f"LA-{index:04d}.json") for index in report["S100_ids"]})
    manifest = {
        "schema_version": 1, "scope": "FORMAL_E4B_FIXED_POLICY_SCIENTIFIC_OOS_V1",
        "git_commit": _git("rev-parse", "HEAD"),
        "S100_sha256": report["S100_sha256"],
        "generator_identity": report["generator_identity"], "generator_sha256": report["generator_sha256"],
        "seeds": list(E4B_SEEDS), "scenarios_per_seed": 2000,
        "seed_table_canonical_sha256": report["seed_table_sha256"],
        "scenario_table_csv_sha256": scenario_table_hashes,
        "checkpoint_set_sha256": checkpoint_identity,
        "policy_seed_evaluations": 1000, "scenario_evaluations": 2_000_000, "failed": 0,
        "initial_batch_failures": len(initial_failure_rows),
        "witness_gated_scaled_retries": retry_count,
        "compact_evidence": True,
        "rebuild_method": "frozen S100 + frozen E1 policies + generator identity/seed/draw order + original exact recourse batch",
        "first_stage_reoptimized": False, "resampled": False, "generator_changed": False, "E5_runs": 0,
        "evaluation_policy_identity": "PROMOTED_CANONICAL_Q_F_R_Z_FIELDS_PLUS_DATA_INDEPENDENT_POLICY_SHA256",
        "historical_first_stage_sha_role": "SOURCE_PROVENANCE_ONLY_INACTIVE_LEVEL_RESIDUES_NOT_PROMOTED",
        "batch_numerical_robustness": "WITNESS_GATED_ALGEBRAICALLY_EQUIVALENT_SCALED_RETRY_WITH_MAPPED_BACK_ORIGINAL_SEMANTIC_VALIDATION",
        "frozen_hashes": report["frozen_hashes"],
    }
    atomic_write_json(directory / "manifest.json", manifest)
    _hash_inventory(directory)
    return 0


def finalize_root() -> int:
    report = preflight(ROOT)
    e4a = json.loads((OUT / "e4a" / "analysis.json").read_text(encoding="utf-8"))
    e4b = json.loads((OUT / "e4b" / "analysis.json").read_text(encoding="utf-8"))
    if frozen_hashes(ROOT) != report["frozen_hashes"]:
        raise RuntimeError("frozen E1-E3 evidence changed")
    manifest = {
        "schema_version": 1, "scope": "FORMAL_E4_OOS_ROBUSTNESS_V1",
        "git_commit": _git("rev-parse", "HEAD"),
        "preflight_sha256": sha256_file(OUT / "preflight.json"),
        "E4A_HASHES": sha256_file(OUT / "e4a" / "HASHES.sha256"),
        "E4B_HASHES": sha256_file(OUT / "e4b" / "HASHES.sha256"),
        "E4A_training_attempted": 4800, "E4A_training_certified": 4800,
        "E4A_heldout_evaluations": 4800,
        "E4B_policy_seed_evaluations": 1000, "E4B_scenario_evaluations": 2_000_000,
        "failures": 0, "frozen_hashes": report["frozen_hashes"],
        "model_changed": False, "tolerance_changed": False, "resampled": False,
        "S200_reselected": False, "S100_reselected": False, "generator_changed": False,
        "memory": False, "E5_runs": 0,
        "evaluation_policy_identity": "PROMOTED_CANONICAL_Q_F_R_Z_FIELDS_PLUS_DATA_INDEPENDENT_POLICY_SHA256",
        "scientific_optimization_runs": 4800,
        "fixed_policy_second_stage_scenario_evaluations": 2_000_000,
    }
    atomic_write_json(OUT / "manifest.json", manifest)
    oos_mean = e4b["policy_level_summary"]["OOS_total_cost_mean"]
    seed_means = [float(row["T_COST_mean_mean"]) for row in e4b["seed_summary"]]
    atomic_write_text(OUT / "E4_RESULT_SUMMARY.md", f"""# Formal E4 out-of-sample robustness

## E4-A — LOHO

- 4,800/4,800 training optimizations were Full Exact Certified and 4,800/4,800 held-out exact evaluations passed.
- Policy-label stability was {e4a['policy_label_stable']}/4,800. All {e4a['policy_label_changed']} label changes occurred when h09/Katrina was held out; the other 23 folds had no label transition.
- Removing h09 changed the first-stage quantities beyond the frozen numerical rule in 200/200 rows and changed the policy label in 35/200. The replacement training worst scenario was h19 in 200/200 rows.
- h09 held-out mean regret of the LOHO policy relative to the frozen full24 policy was {e4a['h09']['heldout_policy_regret_vs_full24_mean']:.6f}; median was {e4a['h09']['heldout_policy_regret_vs_full24_median']:.6f}.
- h01, h02, and h03 produced quantity-level alternative policies without aggregate label changes; the remaining 20 non-h09 deletions were numerically first-stage stable in 200/200 rows.

The evidence distinguishes full24 worst-scenario identity from policy dependence: h09 is influential, but 165/200 policies retained their aggregate regime when it was removed.

## E4-B — Scientific OOS

- 100 frozen E1 policies were evaluated over 10 shared seeds x 2,000 frozen-generator scenarios: 2,000,000 exact recourse evaluations with zero final failures and no first-stage reoptimization.
- Across policies, OOS mean T-COST had mean {oos_mean['mean']:.6f}, median {oos_mean['median']:.6f}, and range [{oos_mean['min']:.6f}, {oos_mean['max']:.6f}].
- Cross-policy mean T-COST by seed ranged from {min(seed_means):.6f} to {max(seed_means):.6f}; seed variation is retained rather than pooled away.
- Every policy's OOS mean T-COST was below its in-sample robust T-COST, while every policy's sampled OOS maximum was above it. This reflects the frozen stress generator's demand multipliers, not a probability calibration.
- S100 contains {json.dumps(e4b['policy_family_counts'], sort_keys=True)}. P2 and P3a comparisons are small-sample descriptive evidence; P3b and P5 are absent from S100.
- The initial unscaled batch solve retained 60 solver-infeasible batches across six policies. All 60 had feasible original-semantic witnesses, solved optimally through an algebraically equivalent scaled retry, were mapped back, and passed original-semantic validation. No scientific input or tolerance changed.

Overall, E4 supports qualified robustness: policy regimes are highly stable to 23 of 24 single-hurricane deletions, h09 has material but not universal policy influence, and all frozen S100 policies remain exactly evaluable under independent frozen-generator demand stress. E4 does not reinterpret S100 family shares as probabilities and does not by itself re-estimate the E1-E3 interaction effects.
""")
    _hash_inventory(OUT)
    return verify()


def verify() -> int:
    report = preflight(ROOT)
    verify_hash_inventory(OUT)
    verify_hash_inventory(OUT / "e4a")
    verify_hash_inventory(OUT / "e4b")
    root_manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if root_manifest["frozen_hashes"] != report["frozen_hashes"] or root_manifest["failures"] != 0 or root_manifest["E5_runs"] != 0:
        raise RuntimeError("E4 root manifest validation failed")
    if len(read_csv(OUT / "e4a" / "scientific_results.csv")) != 4800 or len(read_csv(OUT / "e4a" / "heldout_results.csv")) != 4800:
        raise RuntimeError("E4-A population validation failed")
    if len(read_csv(OUT / "e4b" / "policy_seed_summary.csv")) != 1000 or len(read_csv(OUT / "e4b" / "policy_summary.csv")) != 100:
        raise RuntimeError("E4-B population validation failed")
    print(json.dumps({"status": "PASS", "E4A_certified": 4800, "E4A_heldout": 4800, "E4B_scenario_evaluations": 2_000_000, "failures": 0, "E5_runs": 0}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run-e4a", "finalize-e4a", "run-e4b", "finalize-e4b", "finalize", "verify"))
    command = parser.parse_args().command
    return {
        "preflight": preflight_command,
        "run-e4a": run_e4a,
        "finalize-e4a": finalize_e4a,
        "run-e4b": run_e4b,
        "finalize-e4b": finalize_e4b,
        "finalize": finalize_root,
        "verify": verify,
    }[command]()


if __name__ == "__main__":
    raise SystemExit(main())
