"""Formal E5-A Rawls24 A0 versus Final A1 timing support."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
)
from robust_budget_allocation.algorithms.qfr_protocol import tolerance
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import ITEMS, OUTPUT_ITEMS, SAMPLE_SHA256, load_base_fixture, load_samples
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.e4 import EXPECTED_S200, data_payload_for_sample, preflight as e4_preflight
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


A0_IDENTITY = "R3_V2_A0_STANDARD_CCG"
EXPECTED_REVISION = "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
OUTPUT = Path("formal_results/e5_final")
E5A = OUTPUT / "e5a"
TIMING_REPETITIONS = 3
INSTANCE_COUNT = 200


def frozen_hashes(root: Path) -> dict[str, str]:
    directories = (
        "formal_results/e1_final", "formal_results/e2_final/e2a",
        "formal_results/e2_final/e2b", "formal_results/e2_final/e2c",
        "formal_results/e2_final/e2d", "formal_results/e2_final/e2d_audit",
        "formal_results/e3_final", "formal_results/e3_final/e3a",
        "formal_results/e3_final/e3b", "formal_results/e4_final",
        "formal_results/e4_final/e4a", "formal_results/e4_final/e4b",
    )
    result: dict[str, str] = {}
    for relative in directories:
        directory = root / relative
        verify_hash_inventory(directory)
        result[relative] = sha256_file(directory / "HASHES.sha256")
    return result


def preflight(root: Path) -> dict[str, Any]:
    e4 = e4_preflight(root)
    design = json.loads((root / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
    common, e5 = design["common"], design["E5"]
    if common["dataset"] != "rawls_24_real_single_hurricane_data_recalibration_v1":
        raise ValueError("E5-A Rawls24 identity mismatch")
    if common["scenario_order"] != [f"h{i:02d}" for i in range(1, 25)]:
        raise ValueError("E5-A scenario order mismatch")
    if common["commodities"] != list(ITEMS) or common["model"] != "M2":
        raise ValueError("E5-A item/model identity mismatch")
    if e5["algorithms"] != ["A0", FINAL_A1_IDENTITY] or e5["timing_repetitions"] != 3:
        raise ValueError("E5-A algorithm/timing design mismatch")
    if e5["A"] != {"dataset": "Rawls24", "parameter_subset_size": 200}:
        raise ValueError("E5-A frozen matrix mismatch")
    if FINAL_A1_IMPLEMENTATION_REVISION != EXPECTED_REVISION:
        raise ValueError("Final A1 implementation revision mismatch")
    if design["algorithm"]["memory_enabled"] or design["algorithm"]["memory_metrics_formal"]:
        raise ValueError("Final A1 must be no-memory")
    if e4["S200_sha256"] != EXPECTED_S200 or e4["sample_sha256"] != SAMPLE_SHA256:
        raise ValueError("S200/sample identity mismatch")
    return {
        "status": "PASS", "dataset": "Rawls24", "scenarios": 24, "items": 3,
        "sample_sha256": SAMPLE_SHA256, "S200_sha256": EXPECTED_S200,
        "S200_ids": e4["S200_ids"], "A0_identity": A0_IDENTITY,
        "A1_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "memory_present": False, "timing_repetitions": TIMING_REPETITIONS,
        "instances": INSTANCE_COUNT, "A0_timed_runs": 600, "A1_timed_runs": 600,
        "timing_boundary": "WALL_CLOCK_AROUND_SOLVER_CALL_ONLY",
        "execution_order": "PAIRED_INTERLEAVED_BY_SAMPLE_POSITION_PLUS_REPETITION_PARITY",
        "execution_order_rule": "even parity A0_then_A1; odd parity A1_then_A0",
        "tie_rule": "STRICT_WALL_CLOCK_ORDER_NO_POST_HOC_TIE_BAND",
        "E5B_runs": 0, "E5C_runs": 0, "frozen_hashes": frozen_hashes(root),
    }


def s200_samples(root: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_id = {int(row["sample_index"]): row for row in load_samples(root)}
    return [deepcopy(by_id[int(index)]) for index in report["S200_ids"]]


def data_for_sample(root: Path, sample: Mapping[str, Any]) -> QFRData:
    base, metadata = load_base_fixture(root)
    return QFRData.from_dict(data_payload_for_sample(base, metadata, sample))


def execution_order(position: int, repetition: int) -> tuple[str, str]:
    if position < 1 or repetition not in (1, 2, 3):
        raise ValueError("invalid E5-A position/repetition")
    return ("A0", "A1") if (position + repetition) % 2 == 0 else ("A1", "A0")


def _scientific_decision(result: Mapping[str, Any]) -> dict[str, Any] | None:
    incumbent = result.get("incumbent")
    if not isinstance(incumbent, Mapping):
        return None
    first = incumbent["first_stage"]
    oracle = incumbent["oracle"]
    row: dict[str, Any] = {
        "first_stage_sha256": incumbent["first_stage_sha256"],
        "objective": float(result["objective"]), "worst_loss": float(oracle["worst_loss"]),
        "worst_scenario": str(oracle["worst_scenario"]),
        "full_exact_certificate": bool(oracle.get("complete") and oracle.get("status") == "complete"),
    }
    for item, label in OUTPUT_ITEMS.items():
        row[f"Q_{label}"] = float(first["q"][item])
        row[f"F_{label}"] = sum(float(value) for value in first["f"][item].values())
        active = [int(level) for level, value in first["z"][item].items() if int(value) == 1]
        row[f"R_{label}"] = "NONE" if not active else f"R{active[0]}"
    row["scientific_decision_sha256"] = canonical_json_sha256(row)
    return row


def timing_row(
    sample: Mapping[str, Any], position: int, repetition: int, algorithm: str,
    order_in_pair: int, wall_seconds: float, result: Mapping[str, Any],
) -> dict[str, Any]:
    scientific = _scientific_decision(result)
    row: dict[str, Any] = {
        "simulation_id": sample["simulation_id"], "sample_index": sample["sample_index"],
        "S200_position": position, "input_sha256": sample["input_sha256"],
        "repetition": repetition, "algorithm": algorithm,
        "algorithm_identity": A0_IDENTITY if algorithm == "A0" else FINAL_A1_IDENTITY,
        "implementation_revision": "A0_PRODUCTION" if algorithm == "A0" else FINAL_A1_IMPLEMENTATION_REVISION,
        "order_in_pair": order_in_pair, "wall_clock_seconds": wall_seconds,
        "algorithm_runtime_seconds": float(result["runtime_seconds"]), "status": result["status"],
        "certificate_status": "PASS" if result["status"] == "certified" else "FAIL",
        "failure_message": result.get("diagnostic") or "", "result_sha256": result["result_sha256"],
        "iterations": result["iterations"], "scenario_evaluations": result.get("scenario_evaluations", "unavailable"),
        "exact_oracle_calls": result.get("exact_oracle_calls", "unavailable"),
        "complete_oracle_calls": result.get("complete_oracle_calls", "unavailable"),
        "candidate_hits": result.get("candidate_hits", "unavailable"),
        "full_exact_certification_calls": result.get("full_exact_certification_calls", "unavailable"),
        "complete_full_exact_certification_calls": result.get("complete_full_exact_certification_calls", "unavailable"),
    }
    if scientific is None:
        for key in ("first_stage_sha256", "objective", "worst_loss", "worst_scenario", "full_exact_certificate",
                    "scientific_decision_sha256"):
            row[key] = ""
        for label in OUTPUT_ITEMS.values():
            for prefix in ("Q", "F", "R"):
                row[f"{prefix}_{label}"] = ""
    else:
        row.update(scientific)
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= tolerance(left, right)


def compare_instance(a0: Mapping[str, Any], a1: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "simulation_id": a0["simulation_id"], "sample_index": int(a0["sample_index"]),
        "A0_objective": float(a0["objective"]), "A1_objective": float(a1["objective"]),
    }
    difference = abs(result["A0_objective"] - result["A1_objective"])
    result["absolute_objective_difference"] = difference
    result["objective_tolerance"] = tolerance(result["A0_objective"], result["A1_objective"])
    result["objective_agreement"] = difference <= result["objective_tolerance"]
    max_q, max_f, r_equal = 0.0, 0.0, True
    for label in OUTPUT_ITEMS.values():
        max_q = max(max_q, abs(float(a0[f"Q_{label}"]) - float(a1[f"Q_{label}"])))
        max_f = max(max_f, abs(float(a0[f"F_{label}"]) - float(a1[f"F_{label}"])))
        r_equal = r_equal and a0[f"R_{label}"] == a1[f"R_{label}"]
    result.update(
        max_absolute_Q_difference=max_q, max_absolute_F_difference=max_f, R_equal=r_equal,
        first_stage_hash_equal=a0["first_stage_sha256"] == a1["first_stage_sha256"],
        worst_loss_difference=abs(float(a0["worst_loss"]) - float(a1["worst_loss"])),
        worst_loss_agreement=_close(float(a0["worst_loss"]), float(a1["worst_loss"])),
        worst_scenario_equal=a0["worst_scenario"] == a1["worst_scenario"],
        A0_full_exact_certificate=str(a0["full_exact_certificate"]).lower() == "true",
        A1_full_exact_certificate=str(a1["full_exact_certificate"]).lower() == "true",
    )
    q_equal = all(_close(float(a0[f"Q_{label}"]), float(a1[f"Q_{label}"])) for label in OUTPUT_ITEMS.values())
    f_equal = all(_close(float(a0[f"F_{label}"]), float(a1[f"F_{label}"])) for label in OUTPUT_ITEMS.values())
    result["decision_equivalent"] = q_equal and f_equal and r_equal
    result["classification"] = (
        "SAME_OBJECTIVE_AND_DECISION" if result["objective_agreement"] and result["decision_equivalent"]
        else "OBJECTIVE_EQUIVALENT_DECISION_DIFFERENT_CONSISTENT_WITH_ALTERNATIVE_OPTIMA_OR_DEGENERACY"
        if result["objective_agreement"] else "OBJECTIVE_DISAGREEMENT"
    )
    result["row_sha256"] = canonical_json_sha256(result)
    return result


def distribution(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(map(float, values))
    if not ordered:
        return {}
    def q(p: float) -> float:
        at = (len(ordered) - 1) * p; lo, hi = math.floor(at), math.ceil(at)
        return ordered[lo] if lo == hi else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])
    return {"min": ordered[0], "Q25": q(.25), "median": q(.5), "mean": sum(ordered)/len(ordered),
            "Q75": q(.75), "P90": q(.9), "P95": q(.95), "max": ordered[-1]}


def summarize_runtime(instance_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    a0 = [float(row["A0_median_runtime_seconds"]) for row in instance_rows]
    a1 = [float(row["A1_median_runtime_seconds"]) for row in instance_rows]
    speedup = [left/right for left, right in zip(a0, a1)]
    return {
        "A0": distribution(a0), "A1": distribution(a1), "speedup_A0_over_A1": distribution(speedup),
        "geometric_mean_speedup": math.exp(sum(math.log(value) for value in speedup)/len(speedup)),
        "A1_faster": sum(right < left for left, right in zip(a0, a1)),
        "A0_faster": sum(left < right for left, right in zip(a0, a1)),
        "exact_wall_clock_ties": sum(left == right for left, right in zip(a0, a1)),
        "tie_rule": "STRICT_WALL_CLOCK_ORDER_NO_POST_HOC_TIE_BAND",
    }


def verify_repetitions(rows: Sequence[Mapping[str, Any]]) -> None:
    if len(rows) != 1200:
        raise ValueError("E5-A raw timing population is not 1,200")
    keys = [(row["simulation_id"], row["algorithm"], int(row["repetition"])) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate E5-A timing identity")
    if any(row["certificate_status"] != "PASS" for row in rows):
        raise ValueError("E5-A contains an uncertified timing run")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row["simulation_id"]), str(row["algorithm"])), []).append(row)
    if len(groups) != 400 or any(len(group) != 3 for group in groups.values()):
        raise ValueError("E5-A repetition coverage mismatch")
    for group in groups.values():
        anchor = group[0]
        for row in group[1:]:
            if not _close(float(anchor["objective"]), float(row["objective"])):
                raise ValueError("within-algorithm objective changed across timing repetitions")
            if not _close(float(anchor["worst_loss"]), float(row["worst_loss"])):
                raise ValueError("within-algorithm worst loss changed across timing repetitions")
            for label in OUTPUT_ITEMS.values():
                if not _close(float(anchor[f"Q_{label}"]), float(row[f"Q_{label}"])) or not _close(float(anchor[f"F_{label}"]), float(row[f"F_{label}"])) or anchor[f"R_{label}"] != row[f"R_{label}"]:
                    raise ValueError("within-algorithm decision changed across timing repetitions")


def diagnostic_summary(rows: Sequence[Mapping[str, Any]], algorithm: str) -> dict[str, Any]:
    selected = [row for row in rows if row["algorithm"] == algorithm]
    output = {"timed_runs": len(selected), "iterations": distribution([float(row["iterations"]) for row in selected]),
              "scenario_evaluations": distribution([float(row["scenario_evaluations"]) for row in selected])}
    fields = ("exact_oracle_calls", "complete_oracle_calls") if algorithm == "A0" else (
        "candidate_hits", "full_exact_certification_calls", "complete_full_exact_certification_calls")
    for field in fields:
        output[field] = distribution([float(row[field]) for row in selected])
    return output
