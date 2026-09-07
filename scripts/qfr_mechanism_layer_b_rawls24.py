"""Run paired Rawls24 Layer B and audit h09 dominance without changing Q-F-R draws."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qfr_mechanism_layer_a import (  # noqa: E402
    ITEMS,
    PARAMETERS,
    _csv_bytes,
    _read_samples,
    prepare,
    run,
)
from robust_budget_allocation.algorithms.qfr_protocol import tolerance  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.simulation.layer_a import (  # noqa: E402
    data_for_sample,
    load_config,
    load_rawls24_heterogeneous_fixture,
)


CONFIG = ROOT / "configs/qfr_mechanism_layer_b_rawls24_v1.json"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_b_rawls24_n1000"
POLICIES = ("P1", "P2", "P3a", "P3b", "P4", "P5")
LEVEL_INDEX = {"NONE": -1, "R0": 0, "R1": 1, "R2": 2}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _distribution(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(array)),
        "P10": float(np.quantile(array, 0.10)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "P90": float(np.quantile(array, 0.90)),
        "max": float(np.max(array)),
    }


def _parameter_region(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not rows:
        return "NO_MATCHING_DRAWS"
    return {
        name: {
            "min": min(float(row[name]) for row in rows),
            "median": float(np.median([float(row[name]) for row in rows])),
            "max": max(float(row[name]) for row in rows),
        }
        for name in PARAMETERS
    }


def _load_raw_results(output: Path) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for shard in sorted((output / "raw_a1").glob("*.jsonl.gz")):
        with gzip.open(shard, "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                records[row["simulation_id"]] = row
    if len(records) != 1000:
        raise RuntimeError("Layer B raw result set is not exactly N=1000")
    return records


def _verify_layer_a(config: Mapping[str, Any]) -> Path:
    identity = config["layer_a_pairing"]
    directory = ROOT / identity["directory"]
    expected = {
        "samples.csv": identity["samples_sha256"],
        "scientific_results.csv": identity["scientific_results_sha256"],
        "a1_computational_diagnostics.csv": identity["a1_diagnostics_sha256"],
        "summary.json": identity["summary_sha256"],
        "simulation_manifest.json": identity["manifest_sha256"],
    }
    for name, digest in expected.items():
        if sha256_file(directory / name) != digest:
            raise RuntimeError(f"paired Layer A source hash mismatch: {name}")
    return directory


def _write_layer_b_analysis(
    output: Path, new_summary: dict[str, Any], new_manifest: dict[str, Any]
) -> None:
    config = load_config(CONFIG)
    layer_a_dir = _verify_layer_a(config)
    if sha256_file(output / "samples.csv") != config["layer_a_pairing"]["samples_sha256"]:
        raise RuntimeError("Layer B sample table differs from paired Layer A")
    samples = _read_samples(output / "samples.csv")
    sample_by_id = {row["simulation_id"]: row for row in samples}
    layer_a = {row["simulation_id"]: row for row in _read_csv(layer_a_dir / "scientific_results.csv")}
    layer_b = {row["simulation_id"]: row for row in _read_csv(output / "scientific_results.csv")}
    if list(layer_a) != list(layer_b) or list(layer_b) != list(sample_by_id):
        raise RuntimeError("Layer A/Layer B draw identity or ordering mismatch")
    if any(row["status"] != "SUCCESS" for row in layer_a.values()) or any(
        row["status"] != "SUCCESS" for row in layer_b.values()
    ):
        raise RuntimeError("paired analysis requires 1000 successful Layer A and Layer B rows")
    if any(layer_a[key]["input_sha256"] != layer_b[key]["input_sha256"] for key in layer_a):
        raise RuntimeError("Layer A/Layer B input hashes differ")

    payload, fixture = load_rawls24_heterogeneous_fixture(ROOT, config)
    first_data = data_for_sample(payload, fixture["metadata"], samples[0])
    raw = _load_raw_results(output)
    paired_rows: list[dict[str, Any]] = []
    policy_transitions = {old: {new: 0 for new in POLICIES} for old in POLICIES}
    reliability_transitions = {
        item: {f"{old}->{new}": 0 for old in LEVEL_INDEX for new in LEVEL_INDEX}
        for item in ITEMS
    }
    alternate_counts: dict[str, int] = {}
    for simulation_id in layer_a:
        old, new, sample = layer_a[simulation_id], layer_b[simulation_id], sample_by_id[simulation_id]
        policy_transitions[old["policy_label"]][new["policy_label"]] += 1
        oracle_rows = raw[simulation_id]["a1_result"]["incumbent"]["oracle"]["results"]
        losses = {row["scenario_id"]: float(row["loss"]) for row in oracle_rows}
        h09_loss = losses["h09"]
        alternate_loss = max(value for scenario, value in losses.items() if scenario != "h09")
        alternate = min(
            scenario for scenario, value in losses.items()
            if scenario != "h09" and value == alternate_loss
        )
        alternate_counts[alternate] = alternate_counts.get(alternate, 0) + 1
        row: dict[str, Any] = {
            "simulation_id": simulation_id,
            "sample_index": int(new["sample_index"]),
            "input_sha256": new["input_sha256"],
            "layer_a_policy": old["policy_label"],
            "layer_b_policy": new["policy_label"],
            "policy_transition": f"{old['policy_label']}->{new['policy_label']}",
            "layer_a_T_COST": float(old["objective_T_COST"]),
            "layer_b_T_COST": float(new["objective_T_COST"]),
            "delta_T_COST": float(new["objective_T_COST"]) - float(old["objective_T_COST"]),
            "layer_a_budget_usage": float(old["budget_usage"]),
            "layer_b_budget_usage": float(new["budget_usage"]),
            "delta_budget_usage": float(new["budget_usage"]) - float(old["budget_usage"]),
            "layer_a_worst_scenario": old["worst_scenario"],
            "layer_b_worst_scenario": new["worst_scenario"],
            "h09_recourse_loss": h09_loss,
            "largest_non_h09_recourse_loss": alternate_loss,
            "largest_non_h09_scenario": alternate,
            "h09_loss_advantage": h09_loss - alternate_loss,
            "h09_relative_loss_advantage": (h09_loss - alternate_loss) / max(1.0, abs(h09_loss)),
        }
        for item in ITEMS:
            old_r, new_r = old[f"R_{item}"], new[f"R_{item}"]
            transition = f"{old_r}->{new_r}"
            reliability_transitions[item][transition] += 1
            row.update({
                f"layer_a_Q_{item}": float(old[f"Q_{item}"]),
                f"layer_b_Q_{item}": float(new[f"Q_{item}"]),
                f"delta_Q_{item}": float(new[f"Q_{item}"]) - float(old[f"Q_{item}"]),
                f"layer_a_F_{item}": float(old[f"F_{item}"]),
                f"layer_b_F_{item}": float(new[f"F_{item}"]),
                f"delta_F_{item}": float(new[f"F_{item}"]) - float(old[f"F_{item}"]),
                f"layer_a_R_{item}": old_r,
                f"layer_b_R_{item}": new_r,
                f"reliability_transition_{item}": transition,
                f"delta_R_level_{item}": LEVEL_INDEX[new_r] - LEVEL_INDEX[old_r],
                f"layer_a_worst_exercise_{item}": float(old[f"worst_exercise_{item}"]),
                f"layer_b_worst_exercise_{item}": float(new[f"worst_exercise_{item}"]),
                f"delta_worst_exercise_{item}": float(new[f"worst_exercise_{item}"]) - float(old[f"worst_exercise_{item}"]),
                f"layer_a_worst_shortage_{item}": float(old[f"worst_shortage_{item}"]),
                f"layer_b_worst_shortage_{item}": float(new[f"worst_shortage_{item}"]),
                f"delta_worst_shortage_{item}": float(new[f"worst_shortage_{item}"]) - float(old[f"worst_shortage_{item}"]),
            })
        paired_rows.append(row)
    (output / "paired_layer_a_layer_b.csv").write_bytes(_csv_bytes(paired_rows))

    h09 = "h09"
    scenario_rows: list[dict[str, Any]] = []
    for scenario in first_data.scenarios:
        demand_differences = {
            item: first_data.demand[h09][item] - first_data.demand[scenario][item]
            for item in ITEMS
        }
        exceeds = [item for item, difference in demand_differences.items() if difference < 0]
        q_advantages = [
            float(sample[f"rho_Q{int(fixture['metadata'][scenario]['category'])}"])
            - float(sample["rho_Q5"])
            for sample in samples
        ]
        f_advantages = [
            float(sample[f"rho_F{int(fixture['metadata'][scenario]['category'])}"])
            - float(sample["rho_F5"])
            for sample in samples
        ]
        loss_ratios = []
        times_above_h09 = 0
        for simulation_id in layer_b:
            oracle_rows = raw[simulation_id]["a1_result"]["incumbent"]["oracle"]["results"]
            losses = {entry["scenario_id"]: float(entry["loss"]) for entry in oracle_rows}
            loss_ratios.append(losses[scenario] / max(1.0, losses[h09]))
            times_above_h09 += losses[scenario] > losses[h09] + tolerance(losses[scenario], losses[h09])
        scenario_rows.append({
            "scenario_id": scenario,
            "hurricane_name": fixture["metadata"][scenario]["hurricane_name"],
            "category": fixture["metadata"][scenario]["category"],
            **{f"demand_{item}": first_data.demand[scenario][item] for item in ITEMS},
            **{f"h09_minus_demand_{item}": demand_differences[item] for item in ITEMS},
            "dimensions_exceeding_h09": ";".join(exceeds),
            "h09_componentwise_demand_dominates": not exceeds,
            "q_availability_advantage_over_h09_min": min(q_advantages),
            "q_availability_advantage_over_h09_median": float(np.median(q_advantages)),
            "q_availability_advantage_over_h09_max": max(q_advantages),
            "f_availability_advantage_over_h09_min": min(f_advantages),
            "f_availability_advantage_over_h09_median": float(np.median(f_advantages)),
            "f_availability_advantage_over_h09_max": max(f_advantages),
            "zero_supply_shortage_exposure": sum(
                first_data.shortage_cost[item] * first_data.demand[scenario][item]
                for item in ITEMS
            ),
            "recourse_loss_ratio_to_h09_min": min(loss_ratios),
            "recourse_loss_ratio_to_h09_median": float(np.median(loss_ratios)),
            "recourse_loss_ratio_to_h09_max": max(loss_ratios),
            "times_recourse_loss_above_h09": times_above_h09,
        })
    (output / "h09_scenario_dominance.csv").write_bytes(_csv_bytes(scenario_rows))

    commodity: dict[str, Any] = {}
    tol = float(config["policy_tolerance"])
    for item in ITEMS:
        mixed_ids = [
            row["simulation_id"] for row in paired_rows
            if float(row[f"layer_b_Q_{item}"]) > tol and float(row[f"layer_b_F_{item}"]) > tol
        ]
        commodity[item] = {
            "layer_a_Q_active": sum(float(row[f"layer_a_Q_{item}"]) > tol for row in paired_rows),
            "layer_b_Q_active": sum(float(row[f"layer_b_Q_{item}"]) > tol for row in paired_rows),
            "layer_a_F_active": sum(float(row[f"layer_a_F_{item}"]) > tol for row in paired_rows),
            "layer_b_F_active": sum(float(row[f"layer_b_F_{item}"]) > tol for row in paired_rows),
            "layer_b_Q_and_F_active": len(mixed_ids),
            "layer_b_reliability_counts": {
                level: sum(row[f"layer_b_R_{item}"] == level for row in paired_rows)
                for level in LEVEL_INDEX
            },
            "reliability_transitions": reliability_transitions[item],
            "delta_Q": _distribution([float(row[f"delta_Q_{item}"]) for row in paired_rows]),
            "delta_F": _distribution([float(row[f"delta_F_{item}"]) for row in paired_rows]),
            "delta_R_level": _distribution([float(row[f"delta_R_level_{item}"]) for row in paired_rows]),
            "mixed_parameter_region": _parameter_region([sample_by_id[key] for key in mixed_ids]),
        }
    gaps = [float(row["h09_loss_advantage"]) for row in paired_rows]
    relative_gaps = [float(row["h09_relative_loss_advantage"]) for row in paired_rows]
    mixed_policy_ids = [
        row["simulation_id"] for row in paired_rows
        if row["layer_b_policy"] in {"P2", "P3a", "P3b"}
    ]
    analysis = {
        "scope": "RAWLS24_LAYER_B_PAIRED_HETEROGENEITY_AND_H09_DOMINANCE_AUDIT",
        "sample_table_sha256": sha256_file(output / "samples.csv"),
        "paired_draws": 1000,
        "layer_a_B_ref": float(next(iter(layer_a.values()))["budget"]),
        "layer_b_B_ref": fixture["budget"],
        "heterogeneity": fixture["heterogeneity_source"],
        "h": fixture["h"],
        "a": fixture["a"],
        "tau": fixture["tau"],
        "certification": new_summary["simulation"],
        "policy_counts": new_summary["policy_counts"],
        "policy_transition_matrix": policy_transitions,
        "key_policy_transitions": {
            "Q_only_to_Q_plus_F_R0": sum(row["layer_a_policy"] == "P1" and row["layer_b_policy"] == "P2" for row in paired_rows),
            "Q_only_to_Q_plus_F_paid_R": sum(row["layer_a_policy"] == "P1" and row["layer_b_policy"] in {"P3a", "P3b"} for row in paired_rows),
            "F_dominant_to_mixed_Q_plus_F": sum(row["layer_a_policy"] == "P4" and row["layer_b_policy"] in {"P2", "P3a", "P3b"} for row in paired_rows),
        },
        "commodity_activation": commodity,
        "paired_changes": {
            "delta_T_COST": _distribution([float(row["delta_T_COST"]) for row in paired_rows]),
            "delta_budget_usage": _distribution([float(row["delta_budget_usage"]) for row in paired_rows]),
        },
        "mixed_Q_F": {
            "aggregate_policy_count": len(mixed_policy_ids),
            "parameter_region": _parameter_region([sample_by_id[key] for key in mixed_policy_ids]),
        },
        "h09_dominance": {
            "componentwise_demand_dominates_all_others": all(
                row["h09_componentwise_demand_dominates"] for row in scenario_rows
            ),
            "scenarios_with_any_demand_dimension_above_h09": [
                row["scenario_id"] for row in scenario_rows if row["dimensions_exceeding_h09"]
            ],
            "h09_worst_count": new_summary["scientific"]["worst_scenario_counts"].get("h09", 0),
            "sampled_robust_loss_dominance": all(
                gap >= -tolerance(float(row["h09_recourse_loss"]), float(row["largest_non_h09_recourse_loss"]))
                for gap, row in zip(gaps, paired_rows, strict=True)
            ),
            "strict_positive_loss_advantage_count": sum(gap > 0 for gap in gaps),
            "absolute_loss_advantage": _distribution(gaps),
            "relative_loss_advantage": _distribution(relative_gaps),
            "nearest_non_h09_scenario_counts": alternate_counts,
        },
        "guardrails": {
            "same_draws": True,
            "model_changed": False,
            "algorithm_changed": False,
            "qfr_parameters_retuned": False,
            "formal_e1_e5_executed": False,
            "figures_generated": False,
        },
    }
    analysis["analysis_sha256"] = canonical_json_sha256(analysis)
    (output / "layer_b_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(CONFIG, OUTPUT, load_rawls24_heterogeneous_fixture)
    return run(CONFIG, OUTPUT, load_rawls24_heterogeneous_fixture, _write_layer_b_analysis)


if __name__ == "__main__":
    raise SystemExit(main())
