"""Formal E5-C deterministic commodity-scalability benchmark support."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION
from robust_budget_allocation.algorithms.qfr_protocol import tolerance
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import load_base_fixture, load_samples
from robust_budget_allocation.formal.e4 import rawls24_templates
from robust_budget_allocation.formal.e5a import A0_IDENTITY, E5A, EXPECTED_REVISION, frozen_hashes, preflight as e5a_preflight
from robust_budget_allocation.formal.final_design import (
    E5C_GENERATOR_IDENTITY, RNG_IDENTITY, canonical_sha256, e5c_budget, generate_e5c_items,
)
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


EXPECTED_GENERATOR_SHA256 = "793e094c80454655f58e752e404c82cde654578775bff54d5aa722ae30ba4736"
SEEDS = tuple(range(20261101, 20261131))
SIZES = (3, 6, 9)
E5C = Path("formal_results/e5_final/e5c")
ARCHETYPE_SOURCE = {
    "Standard": "Water", "Preservation": "Seasonal Influenza Vaccine", "StorageLoss": "Crackers",
}


def _demand_matrix(master: Sequence[Mapping[str, Any]], scenarios: Sequence[Mapping[str, Any]], size: int) -> list[dict[str, Any]]:
    return [{"scenario_id": row["scenario_id"], "demand": {
        item["item_id"]: row["demand"][item["item_id"]] for item in master[:size]
    }} for row in scenarios]


def preflight(root: Path) -> dict[str, Any]:
    inherited = e5a_preflight(root)
    verify_hash_inventory(root / E5A)
    e5a_hash = sha256_file(root / E5A / "HASHES.sha256")
    e5b = root / "formal_results/e5_final/e5b"
    verify_hash_inventory(e5b)
    e5b_hash = sha256_file(e5b / "HASHES.sha256")
    root_manifest = json.loads((root / "formal_results/e5_final/manifest.json").read_text(encoding="utf-8"))
    if root_manifest["E5A_hash_inventory_sha256"] != e5a_hash or root_manifest["E5B_hash_inventory_sha256"] != e5b_hash:
        raise ValueError("frozen E5-A/E5-B hash inventory mismatch")
    design = json.loads((root / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
    machine = json.loads((root / "docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json").read_text(encoding="utf-8"))
    frozen, identity = design["E5"]["C"], machine["E5C"]
    if frozen["generator_identity"] != E5C_GENERATOR_IDENTITY or identity["identity"] != E5C_GENERATOR_IDENTITY:
        raise ValueError("E5-C generator identity mismatch")
    if identity["generator_sha256"] != EXPECTED_GENERATOR_SHA256:
        raise ValueError("E5-C generator hash mismatch")
    if canonical_sha256({k: v for k, v in identity.items() if k != "generator_sha256"}) != EXPECTED_GENERATOR_SHA256:
        raise ValueError("E5-C machine identity body hash mismatch")
    if tuple(frozen["seeds"]) != SEEDS or frozen["item_sizes"] != list(SIZES) or frozen["scenarios"] != 100:
        raise ValueError("E5-C seed/dimension design mismatch")
    if frozen["replicates_per_size"] != 30 or frozen["nested_master_items"] != 9:
        raise ValueError("E5-C replicate/master design mismatch")
    if frozen["item_order"] != identity["item_order"] or frozen["extra_item_by_scenario_multiplier"]:
        raise ValueError("E5-C nesting/noise design mismatch")
    if FINAL_A1_IDENTITY != "A1_FINAL_NO_MEMORY_V1" or FINAL_A1_IMPLEMENTATION_REVISION != EXPECTED_REVISION:
        raise ValueError("E5-C Final A1 identity mismatch")
    templates = rawls24_templates(root)
    rebuilt = []
    for expected, seed in zip(identity["replicates"], SEEDS, strict=True):
        generated = generate_e5c_items(seed, templates)
        master, scenarios = generated["master_9"], generated["master_100"]
        actual = {
            "seed": seed, "parameter_row_id": generated["parameter_row_id"],
            "master_9_sha256": canonical_sha256(master),
            "master_100_scenario_sha256": canonical_sha256(scenarios),
            "prefix_sha256": {str(size): canonical_sha256(master[:size]) for size in SIZES},
            "demand_matrix_sha256": {str(size): canonical_sha256(_demand_matrix(master, scenarios, size)) for size in SIZES},
            "B_ref_bench": {str(size): e5c_budget(master, scenarios, size) for size in SIZES},
        }
        if actual != expected:
            raise ValueError(f"E5-C frozen replicate identity mismatch: {seed}")
        rebuilt.append(actual)
    return {
        "status": "PASS", "generator_identity": E5C_GENERATOR_IDENTITY,
        "generator_sha256": EXPECTED_GENERATOR_SHA256, "rng_identity": RNG_IDENTITY,
        "seeds": list(SEEDS), "item_sizes": list(SIZES), "replicates": rebuilt,
        "parameter_row_ids": [row["parameter_row_id"] for row in rebuilt],
        "scenarios": 100, "unique_instances": 90, "timing_repetitions": 3,
        "A0_identity": A0_IDENTITY, "A1_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION, "memory_present": False,
        "A0_timed_runs": 270, "A1_timed_runs": 270,
        "budget_rule": "B_EQUALS_SIZE_SPECIFIC_B_REF_BENCH_RATIO_1",
        "nested_items_verified": True, "shared_scenarios_verified": True,
        "no_hurricane": True, "extra_item_by_scenario_noise": False, "extra_availability_noise": False,
        "timing_boundary": inherited["timing_boundary"], "execution_order": inherited["execution_order"],
        "tie_rule": inherited["tie_rule"], "E5A_hash_inventory_sha256": e5a_hash,
        "E5B_hash_inventory_sha256": e5b_hash, "frozen_hashes": frozen_hashes(root),
    }


def generated_replicate(root: Path, seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("unknown E5-C seed")
    return generate_e5c_items(seed, rawls24_templates(root))


def sample_by_id(root: Path, row_id: int) -> dict[str, Any]:
    return deepcopy(load_samples(root)[row_id - 1])


def data_for_instance(root: Path, generated: Mapping[str, Any], sample: Mapping[str, Any], size: int) -> QFRData:
    if size not in SIZES:
        raise ValueError("invalid E5-C item size")
    base, _ = load_base_fixture(root)
    selected = list(generated["master_9"][:size])
    scenarios = list(generated["master_100"])
    items = [str(row["item_id"]) for row in selected]
    by_id = {str(row["item_id"]): row for row in selected}
    source = {item: ARCHETYPE_SOURCE[str(by_id[item]["archetype"])] for item in items}
    q_cost = {item: float(base["q_unit_cost"][source[item]]) * float(by_id[item]["m_c"]) for item in items}
    payload = deepcopy(base)
    payload["items"] = items
    payload["scenarios"] = [str(row["scenario_id"]) for row in scenarios]
    payload["budget"] = e5c_budget(generated["master_9"], scenarios, size)
    payload["q_unit_cost"] = q_cost
    payload["storage_cost"] = {item: float(by_id[item]["h_times_tau"]) / float(base["tau"]) for item in items}
    payload["retention"] = {item: float(by_id[item]["a"]) for item in items}
    payload["flexible_capacity"] = {item: max(float(row["demand"][item]) for row in scenarios) for item in items}
    payload["reservation_cost"] = {item: float(sample["phi"]) * q_cost[item] for item in items}
    payload["exercise_cost"] = {item: float(sample["psi"]) * q_cost[item] for item in items}
    payload["shortage_cost"] = {item: 4.0 * q_cost[item] for item in items}
    payload["reliability_cost"] = {item: {
        "0": 0.0, "1": float(sample["c_R1_ratio"]) * q_cost[item],
        "2": float(sample["c_R2_ratio"]) * q_cost[item],
    } for item in items}
    payload["reliability_mitigation"] = {item: {
        "0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"]),
    } for item in items}
    payload["demand"] = {str(row["scenario_id"]): {item: float(row["demand"][item]) for item in items} for row in scenarios}
    payload["q_availability"] = {}
    payload["disruption"] = {}
    for row in scenarios:
        sid, category = str(row["scenario_id"]), int(row["category"])
        payload["q_availability"][sid] = dict.fromkeys(items, float(sample[f"rho_Q{category}"]))
        payload["disruption"][sid] = dict.fromkeys(items, 1.0 - float(sample[f"rho_F{category}"]))
    return QFRData.from_dict(payload)


def scientific_decision(result: Mapping[str, Any]) -> dict[str, Any] | None:
    incumbent = result.get("incumbent")
    if not isinstance(incumbent, Mapping):
        return None
    first, oracle = incumbent["first_stage"], incumbent["oracle"]
    decisions = {}
    for item in first["q"]:
        active = [int(level) for level, value in first["z"][item].items() if int(value) == 1]
        decisions[item] = {
            "Q": float(first["q"][item]), "F": sum(float(value) for value in first["f"][item].values()),
            "R": "NONE" if not active else f"R{active[0]}",
        }
    row = {
        "first_stage_sha256": incumbent["first_stage_sha256"], "objective": float(result["objective"]),
        "worst_loss": float(oracle["worst_loss"]), "worst_scenario": str(oracle["worst_scenario"]),
        "full_exact_certificate": bool(oracle.get("complete") and oracle.get("status") == "complete"),
        "decisions_json": json.dumps(decisions, sort_keys=True, separators=(",", ":")),
    }
    row["scientific_decision_sha256"] = canonical_json_sha256(row)
    return row


def compare_instance(a0: Mapping[str, Any], a1: Mapping[str, Any]) -> dict[str, Any]:
    objective_difference = abs(float(a0["objective"]) - float(a1["objective"]))
    d0, d1 = json.loads(str(a0["decisions_json"])), json.loads(str(a1["decisions_json"]))
    max_q = max(abs(float(d0[item]["Q"]) - float(d1[item]["Q"])) for item in d0)
    max_f = max(abs(float(d0[item]["F"]) - float(d1[item]["F"])) for item in d0)
    r_equal = all(d0[item]["R"] == d1[item]["R"] for item in d0)
    decision_equivalent = all(
        abs(float(d0[item][field]) - float(d1[item][field])) <= tolerance(float(d0[item][field]), float(d1[item][field]))
        for item in d0 for field in ("Q", "F")
    ) and r_equal
    result = {
        "A0_objective": float(a0["objective"]), "A1_objective": float(a1["objective"]),
        "absolute_objective_difference": objective_difference,
        "objective_tolerance": tolerance(float(a0["objective"]), float(a1["objective"])),
        "objective_agreement": objective_difference <= tolerance(float(a0["objective"]), float(a1["objective"])),
        "max_absolute_Q_difference": max_q, "max_absolute_F_difference": max_f, "R_equal": r_equal,
        "first_stage_hash_equal": a0["first_stage_sha256"] == a1["first_stage_sha256"],
        "worst_loss_difference": abs(float(a0["worst_loss"]) - float(a1["worst_loss"])),
        "worst_loss_agreement": abs(float(a0["worst_loss"]) - float(a1["worst_loss"])) <= tolerance(float(a0["worst_loss"]), float(a1["worst_loss"])),
        "worst_scenario_equal": a0["worst_scenario"] == a1["worst_scenario"],
        "A0_full_exact_certificate": str(a0["full_exact_certificate"]).lower() == "true",
        "A1_full_exact_certificate": str(a1["full_exact_certificate"]).lower() == "true",
        "decision_equivalent": decision_equivalent,
    }
    result["classification"] = "SAME_OBJECTIVE_AND_DECISION" if result["objective_agreement"] and decision_equivalent else (
        "OBJECTIVE_EQUIVALENT_DECISION_DIFFERENT_CONSISTENT_WITH_ALTERNATIVE_OPTIMA_OR_DEGENERACY"
        if result["objective_agreement"] else "OBJECTIVE_DISAGREEMENT"
    )
    result["row_sha256"] = canonical_json_sha256(result)
    return result


def verify_timing_population(rows: Sequence[Mapping[str, Any]]) -> None:
    if len(rows) != 540:
        raise ValueError("E5-C raw timing population is not 540")
    keys = [(r["benchmark_instance_id"], r["algorithm"], r["repetition"]) for r in rows]
    if len(keys) != len(set(keys)) or any(r["certificate_status"] != "PASS" for r in rows):
        raise ValueError("E5-C timing identity/certification failure")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row["benchmark_instance_id"]), str(row["algorithm"])), []).append(row)
    if len(groups) != 180 or any(len(group) != 3 for group in groups.values()):
        raise ValueError("E5-C repetition coverage mismatch")
    for group in groups.values():
        anchor = group[0]
        for row in group[1:]:
            if abs(float(anchor["objective"]) - float(row["objective"])) > tolerance(float(anchor["objective"]), float(row["objective"])):
                raise ValueError("E5-C repeated objective mismatch")
            if abs(float(anchor["worst_loss"]) - float(row["worst_loss"])) > tolerance(float(anchor["worst_loss"]), float(row["worst_loss"])):
                raise ValueError("E5-C repeated worst-loss mismatch")


def growth_distribution(values: Sequence[float]) -> dict[str, float]:
    """Frozen descriptive distribution for positive scaling ratios."""
    ordered = sorted(map(float, values))
    if not ordered or any(value <= 0 for value in ordered):
        raise ValueError("growth ratios must be positive and nonempty")
    def q(p: float) -> float:
        at = (len(ordered) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return ordered[lo] if lo == hi else ordered[lo] + (at - lo) * (ordered[hi] - ordered[lo])
    return {
        "min": ordered[0], "Q25": q(.25), "median": q(.5),
        "mean": sum(ordered) / len(ordered),
        "geometric_mean": math.exp(sum(math.log(value) for value in ordered) / len(ordered)),
        "Q75": q(.75), "P90": q(.9), "P95": q(.95), "max": ordered[-1],
    }
