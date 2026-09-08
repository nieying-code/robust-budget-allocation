"""Static PR #27 Layer B -> Final E1 identity audit; never calls an optimizer."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FINAL_CONFIG = ROOT / "configs/final_formal_scientific_design_v1.json"
FINAL_PROTOCOL = ROOT / "docs/FINAL_FORMAL_SCIENTIFIC_DESIGN_v1.md"
PR_HEAD = "675759cf955788d0200e8c1f24e7e1aff13af44b"
PR_NUMBER = 27
PR_OUTPUT = "simulation_results/qfr_mechanism_layer_b_rawls24_n1000"
PARAMETERS = (
    "rho_Q1", "rho_Q2", "rho_Q3", "rho_Q4", "rho_Q5",
    "rho_F1", "rho_F2", "rho_F3", "rho_F4", "rho_F5",
    "eta_1", "eta_2", "phi", "psi", "c_R1_ratio", "c_R2_ratio",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True, capture_output=True
    ).stdout


def _json_blob(commit: str, path: str) -> dict[str, Any]:
    return json.loads(_git_blob(commit, path).decode("utf-8"))


def _csv_blob(commit: str, path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(_git_blob(commit, path).decode("utf-8"))))


def _check(identifier: str, label: str, passed: bool, evidence: Any) -> dict[str, Any]:
    return {"id": identifier, "field": label, "status": "PASS" if passed else "FAIL", "evidence": evidence}


def _canonical_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _lhs_values(rng: np.random.Generator, n: int, low: float, high: float) -> list[float]:
    unit = (np.arange(n, dtype=float) + rng.random(n)) / n
    values = low + (high - low) * unit
    rng.shuffle(values)
    return [float(value) for value in values]


def _assign_below(rng: np.random.Generator, upper: list[float], values: list[float]) -> list[float]:
    ordered, pool, cursor = sorted(values), [], 0
    result = [0.0] * len(upper)
    for row in sorted(range(len(upper)), key=lambda index: (upper[index], index)):
        while cursor < len(ordered) and ordered[cursor] <= upper[row]:
            pool.append(ordered[cursor]); cursor += 1
        if not pool:
            raise ValueError("constrained LHS descending match failed")
        result[row] = pool.pop(int(rng.integers(len(pool))))
    if cursor != len(ordered) or pool:
        raise ValueError("constrained LHS descending match incomplete")
    return result


def _assign_above(rng: np.random.Generator, lower: list[float], values: list[float]) -> list[float]:
    ordered, pool, cursor = sorted(values, reverse=True), [], 0
    result = [0.0] * len(lower)
    for row in sorted(range(len(lower)), key=lambda index: (-lower[index], index)):
        while cursor < len(ordered) and ordered[cursor] >= lower[row]:
            pool.append(ordered[cursor]); cursor += 1
        if not pool:
            raise ValueError("constrained LHS ordered-pair match failed")
        result[row] = pool.pop(int(rng.integers(len(pool))))
    if cursor != len(ordered) or pool:
        raise ValueError("constrained LHS ordered-pair match incomplete")
    return result


def _reconstruct_samples(config: dict[str, Any]) -> bytes:
    n, seed, bounds = int(config["sample_size"]), int(config["seed"]), config["bounds"]
    rng = np.random.Generator(np.random.PCG64(seed))
    curves: dict[str, list[float]] = {}
    for prefix in ("rho_Q", "rho_F"):
        names = [f"{prefix}{index}" for index in range(1, 6)]
        columns = {name: _lhs_values(rng, n, *map(float, bounds[name])) for name in names}
        curves[names[0]] = columns[names[0]]
        for previous, name in zip(names, names[1:], strict=False):
            curves[name] = _assign_below(rng, curves[previous], columns[name])
    eta1 = _lhs_values(rng, n, *map(float, bounds["eta_1"]))
    eta2 = _assign_above(rng, [value + .05 for value in eta1], _lhs_values(rng, n, *map(float, bounds["eta_2"])))
    premium1 = _lhs_values(rng, n, *map(float, bounds["c_R1_ratio"]))
    premium2 = _assign_above(rng, [value + .05 for value in premium1], _lhs_values(rng, n, *map(float, bounds["c_R2_ratio"])))
    phi = _lhs_values(rng, n, *map(float, bounds["phi"]))
    psi = _lhs_values(rng, n, *map(float, bounds["psi"]))
    rows: list[dict[str, Any]] = []
    for index in range(n):
        row: dict[str, Any] = {"simulation_id": f"LA-{index+1:04d}", "sample_index": index+1, "simulation_seed": seed}
        row.update({name: curves[name][index] for name in curves})
        row.update({"eta_1": eta1[index], "eta_2": eta2[index], "phi": phi[index], "psi": psi[index], "c_R1_ratio": premium1[index], "c_R2_ratio": premium2[index]})
        row["input_sha256"] = _canonical_sha(row)
        rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["simulation_id", "sample_index", "simulation_seed", *PARAMETERS, "input_sha256"], lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build_audit() -> dict[str, Any]:
    final = json.loads(FINAL_CONFIG.read_text(encoding="utf-8"))
    pr_config = _json_blob(PR_HEAD, "configs/qfr_mechanism_layer_b_rawls24_v1.json")
    manifest = _json_blob(PR_HEAD, f"{PR_OUTPUT}/simulation_manifest.json")
    summary = _json_blob(PR_HEAD, f"{PR_OUTPUT}/summary.json")
    samples_blob = _git_blob(PR_HEAD, f"{PR_OUTPUT}/samples.csv")
    reconstructed_samples = _reconstruct_samples(pr_config)
    reproduced_again = _reconstruct_samples(pr_config)
    scientific = _csv_blob(PR_HEAD, f"{PR_OUTPUT}/scientific_results.csv")
    diagnostics = _csv_blob(PR_HEAD, f"{PR_OUTPUT}/a1_computational_diagnostics.csv")
    inputs = list(csv.DictReader((ROOT / "data/r6_rawls24/unified_hurricane_input.csv").open(encoding="utf-8", newline="")))
    scenario_order = [row["scenario_id"] for row in inputs]
    formal = json.loads((ROOT / "configs/r6c_formal_ready_data_v2.json").read_text(encoding="utf-8"))["qfr_data"]

    hashes_text = _git_blob(PR_HEAD, f"{PR_OUTPUT}/HASHES.sha256").decode("utf-8")
    artifact_hashes: dict[str, str] = {}
    artifact_hash_failures: list[str] = []
    for line in hashes_text.splitlines():
        digest, name = line.split("  ", 1)
        artifact_hashes[name] = digest
        if _sha(_git_blob(PR_HEAD, f"{PR_OUTPUT}/{name}")) != digest:
            artifact_hash_failures.append(name)

    memory = {
        "solve_count": 0,
        "memory_phase_enabled_count": 0,
        "memory_opportunities": 0,
        "memory_hits": 0,
        "memory_planned_evaluations": 0,
        "memory_exact_evaluations": 0,
        "iterations_with_memory_evaluation": 0,
        "candidate_plan_changes_vs_memory_disabled": 0,
        "full_exact_after_memory_miss": 0,
    }
    method_counts: dict[str, int] = {}
    for shard_index in range(1, 41):
        raw = gzip.decompress(
            _git_blob(PR_HEAD, f"{PR_OUTPUT}/raw_a1/a1_results_{shard_index:03d}.jsonl.gz")
        ).decode("utf-8")
        for line in raw.splitlines():
            record = json.loads(line)
            result = record["a1_result"]
            memory["solve_count"] += 1
            enabled = result["settings"]["memory_phase_enabled"] is True
            memory["memory_phase_enabled_count"] += enabled
            memory["memory_opportunities"] += int(result["memory_opportunities"])
            memory["memory_hits"] += int(result["memory_hits"])
            method_counts[result["method"]] = method_counts.get(result["method"], 0) + 1
            canonical = result["canonical_scenarios"]
            for trace in result["trace"]:
                phase = trace.get("memory") or {}
                evaluations = phase.get("evaluations") or []
                memory["memory_planned_evaluations"] += len(phase.get("planned") or [])
                memory["memory_exact_evaluations"] += len(evaluations)
                if not evaluations:
                    continue
                memory["iterations_with_memory_evaluation"] += 1
                active = set(trace["active_scenarios"])
                no_memory_first = next((sid for sid in canonical if sid not in active), None)
                candidate = trace.get("candidate") or {}
                actual_first = (candidate.get("planned") or [None])[0]
                memory["candidate_plan_changes_vs_memory_disabled"] += actual_first != no_memory_first
                memory["full_exact_after_memory_miss"] += (
                    not phase.get("hit") and trace.get("full_exact_certification") is not None
                )

    expected_h = final["common"]["commodity_baseline"]
    expected_bounds = final["E1"]["bounds"]
    expected_constraints = final["E1"]["constraints"]
    actual_items = formal["items"]
    actual_lambda = [
        formal["shortage_cost"][item] / (4.0 * formal["q_unit_cost"][item])
        for item in actual_items
    ]
    code = _git_blob(PR_HEAD, "scripts/qfr_mechanism_layer_a.py").decode("utf-8")
    numerical = _git_blob(
        PR_HEAD, "src/robust_budget_allocation/algorithms/qfr_numerical_validation.py"
    ).decode("utf-8")
    protocol = _git_blob(PR_HEAD, "src/robust_budget_allocation/algorithms/qfr_protocol.py").decode("utf-8")

    checks = [
        _check("01", "dataset identity", manifest["fixture"]["dataset_identity"] == final["common"]["dataset"], manifest["fixture"]["dataset_identity"]),
        _check("02", "Rawls24 scenario identity", len(scenario_order) == 24 and all(row["scenario_type"] == "single_hurricane" for row in inputs), scenario_order),
        _check("03", "scenario order", manifest["fixture"]["scenario_order"] == final["common"]["scenario_order"] == scenario_order, scenario_order),
        _check("04", "commodity identity", actual_items == final["common"]["commodities"], actual_items),
        _check("05", "commodity static parameters", pr_config["source"]["economic_template"]["sha256"] == _sha((ROOT / "configs/r6c_formal_ready_data_v2.json").read_bytes()), pr_config["source"]["economic_template"]),
        _check("06", "demand mapping", manifest["fixture"]["demand_mapping"] == {"Water": "water_unified", "Seasonal Influenza Vaccine": "medical_unified * 10.0603621730382", "Crackers": "food_unified * 14"}, manifest["fixture"]["demand_mapping"]),
        _check("07", "h/a values", manifest["fixture"]["h"] == {item: expected_h[item]["h_per_month"] for item in actual_items} and manifest["fixture"]["a"] == {item: expected_h[item]["a"] for item in actual_items}, {"h": manifest["fixture"]["h"], "a": manifest["fixture"]["a"]}),
        _check("08", "beta", pr_config["fixed_environment"]["shortage_beta"] == final["common"]["beta"], pr_config["fixed_environment"]["shortage_beta"]),
        _check("09", "lambda", all(abs(left-right) < 1e-12 for left, right in zip(actual_lambda, final["common"]["lambda"])), actual_lambda),
        _check("10", "absolute B", manifest["fixture"]["budget"] == final["common"]["B_ref_E1"], manifest["fixture"]["budget"]),
        _check("11", "B_ref definition", manifest["fixture"]["B_ref_formula"] == "sum_i((cQ_i+h_i*tau)*Dref_i/a_i)", manifest["fixture"]["B_ref_formula"]),
        _check("12", "parameter-table identity", len(scientific) == 1000 and [row["simulation_id"] for row in scientific] == [f"LA-{index:04d}" for index in range(1,1001)], {"rows": len(scientific), "first": scientific[0]["simulation_id"], "last": scientific[-1]["simulation_id"]}),
        _check("13", "parameter-table SHA-256 and deterministic reconstruction", _sha(samples_blob) == final["E1"]["sample_table_sha256"] and reconstructed_samples == samples_blob and reproduced_again == reconstructed_samples, {"committed": _sha(samples_blob), "reconstructed": _sha(reconstructed_samples), "byte_identical": reconstructed_samples == samples_blob}),
        _check("14", "seed", pr_config["seed"] == final["E1"]["seed"], pr_config["seed"]),
        _check("15", "sampling method", pr_config["sampling_method"] == final["E1"]["sampling"], pr_config["sampling_method"]),
        _check("16", "parameter ranges", pr_config["bounds"] == expected_bounds, pr_config["bounds"]),
        _check("17", "monotonic/order constraints", all(pr_config["constraints"][key] == expected_constraints[key] for key in ("rho_Q","rho_F","eta","reliability_premium")), pr_config["constraints"]),
        _check("18", "M2 model identity", pr_config["model_kind"] == manifest["model_kind"] == final["common"]["model"], manifest["model_kind"]),
        _check("19", "A1 mathematical identity", summary["simulation"]["certified"] == 1000 and method_counts == {"R4_V2_A1_IMPROVED_CCG": 1000}, {"method_counts": method_counts, "candidate_hits": summary["computational"]["candidate_hits_total"], "full_exact_calls": summary["computational"]["full_exact_certification_calls_total"]}),
        _check("20", "A1 Memory status for scientific reuse", memory["memory_hits"] == 0 and memory["candidate_plan_changes_vs_memory_disabled"] == 0 and memory["full_exact_after_memory_miss"] == 1000, memory),
        _check("21", "numerically robust exact oracle/validation", "VALIDATION_RELATIVE_TOLERANCE = 1e-12" in numerical and "violation_is_acceptable" in numerical and summary["simulation"]["certified"] == 1000, {"validation_rule": "1e-7 + 1e-12*family_scale", "certified": summary["simulation"]["certified"]}),
        _check("22", "tolerances", "ABSOLUTE_TOLERANCE = 1e-7" in protocol and "RELATIVE_TOLERANCE = 1e-9" in protocol and pr_config["policy_tolerance"] == final["E1"]["policy_tolerance"], {"convergence": "1e-7+1e-9*scale", "validation": "1e-7+1e-12*family_scale", "policy": pr_config["policy_tolerance"]}),
        _check("23", "solver policy", manifest["environment"]["solver_interface"] == "gurobi_direct" and manifest["environment"]["threads"] == 1 and all(token in protocol for token in ('"MIPGap": 0','"FeasibilityTol": 1e-9','"OptimalityTol": 1e-9','"IntFeasTol": 1e-9')), manifest["environment"]),
        _check("24", "result schema", len(scientific) == len(diagnostics) == 1000 and all(row["status"] == "SUCCESS" and row["certificate_status"] == "PASS" for row in scientific) and all(f"Q_{item}" in scientific[0] and f"F_{item}" in scientific[0] and f"R_{item}" in scientific[0] for item in actual_items), {"scientific_rows": len(scientific), "diagnostic_rows": len(diagnostics), "artifact_hash_entries_verified": len(artifact_hashes), "artifact_hash_failures": artifact_hash_failures}),
        _check("25", "scientific output interpretation", pr_config["scientific_status"] == "EXPLORATORY_LAYER_B_NOT_FORMAL_E1_E5" and "parameter_tuning" in manifest["guardrails"] and not manifest["guardrails"]["parameter_tuning"], {"status": pr_config["scientific_status"], "parameter_tuning": manifest["guardrails"]["parameter_tuning"]}),
    ]
    reuse = all(row["status"] == "PASS" for row in checks)
    policy_tolerance = float(final["E1"]["policy_tolerance"])
    f_active_row_ids = [
        int(row["sample_index"])
        for row in scientific
        if any(
            float(row[f"F_{item}"]) > policy_tolerance
            for item in ("Water", "Seasonal Influenza Vaccine", "Crackers")
        )
    ]
    return {
        "schema_version": 1,
        "scope": "PR27_LAYER_B_TO_FINAL_E1_STATIC_IDENTITY_AUDIT",
        "audit_kind": "SOLVER_FREE_STATIC_COMMITTED_ARTIFACT_AUDIT",
        "pr_number": PR_NUMBER,
        "pr_head": PR_HEAD,
        "pr_output_root": PR_OUTPUT,
        "final_protocol_sha256": _sha(FINAL_PROTOCOL.read_bytes()),
        "final_config_sha256": _sha(FINAL_CONFIG.read_bytes()),
        "sample_table_sha256": _sha(samples_blob),
        "f_active_filter_evidence": {
            "definition": "any commodity F_i > Final E1 policy_tolerance",
            "policy_tolerance": policy_tolerance,
            "row_count": len(f_active_row_ids),
            "row_ids": f_active_row_ids,
        },
        "sampler_reconstruction": {
            "method": "INDEPENDENT_STATIC_REIMPLEMENTATION_OF_COMMITTED_PR27_SAMPLER",
            "same_seed_byte_identical_twice": reconstructed_samples == reproduced_again,
            "reconstructed_sha256": _sha(reconstructed_samples),
            "matches_committed_sample_bytes": reconstructed_samples == samples_blob,
        },
        "pr_artifact_hash_entries_verified": len(artifact_hashes),
        "pr_artifact_hash_failures": artifact_hash_failures,
        "memory_effect_audit": memory,
        "checks": checks,
        "counts": {"PASS": sum(row["status"] == "PASS" for row in checks), "FAIL": sum(row["status"] == "FAIL" for row in checks), "UNKNOWN": 0},
        "FINAL_E1_REUSE_CANDIDATE": "YES" if reuse else "NO",
        "reuse_scope": "E1_SCIENTIFIC_OUTPUTS_ONLY_PENDING_INDEPENDENT_APPROVAL" if reuse else "NOT_REUSABLE",
        "excluded_reuse": ["E5 runtime", "E5 scenario-evaluation counts", "Memory metrics", "formal algorithm-label identity"],
        "scientific_optimization_runs": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audit = build_audit()
    payload = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0 if audit["counts"]["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
