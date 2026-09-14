"""Formal E5-B deterministic scenario-scalability benchmark support."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import FINAL_A1_IDENTITY, FINAL_A1_IMPLEMENTATION_REVISION
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import ITEMS, load_base_fixture, load_samples
from robust_budget_allocation.formal.e4 import rawls24_templates
from robust_budget_allocation.formal.e5a import A0_IDENTITY, E5A, EXPECTED_REVISION, frozen_hashes, preflight as e5a_preflight
from robust_budget_allocation.formal.final_design import (
    E5B_GENERATOR_IDENTITY, RNG_IDENTITY, benchmark_budget, canonical_sha256, generate_e5b,
)
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.io.hashing import sha256_file


EXPECTED_GENERATOR_SHA256 = "e45edd2c957b7f0f46969773f8d36821a127d4da72ed5fe8ec7e6b93906c4b32"
SEEDS = tuple(range(20261001, 20261031))
SIZES = (50, 100, 200, 500)
E5B = Path("formal_results/e5_final/e5b")


def preflight(root: Path) -> dict[str, Any]:
    inherited = e5a_preflight(root)
    verify_hash_inventory(root / E5A)
    e5a_hash = sha256_file(root / E5A / "HASHES.sha256")
    root_manifest = json.loads((root / "formal_results/e5_final/manifest.json").read_text(encoding="utf-8"))
    if root_manifest["E5A_hash_inventory_sha256"] != e5a_hash:
        raise ValueError("frozen E5-A hash inventory mismatch")
    design = json.loads((root / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
    machine = json.loads((root / "docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json").read_text(encoding="utf-8"))
    frozen, identity = design["E5"]["B"], machine["E5B"]
    if frozen["generator_identity"] != E5B_GENERATOR_IDENTITY or identity["identity"] != E5B_GENERATOR_IDENTITY:
        raise ValueError("E5-B generator identity mismatch")
    if identity["generator_sha256"] != EXPECTED_GENERATOR_SHA256:
        raise ValueError("E5-B generator hash mismatch")
    body = {key: value for key, value in identity.items() if key != "generator_sha256"}
    if canonical_sha256(body) != EXPECTED_GENERATOR_SHA256:
        raise ValueError("E5-B machine identity body hash mismatch")
    if tuple(frozen["seeds"]) != SEEDS or frozen["scenario_sizes"] != list(SIZES) or frozen["replicates_per_size"] != 30:
        raise ValueError("E5-B seed/size/replicate design mismatch")
    if frozen["items"] != 3 or frozen["nested_master_size"] != 500:
        raise ValueError("E5-B dimension design mismatch")
    if FINAL_A1_IDENTITY != "A1_FINAL_NO_MEMORY_V1" or FINAL_A1_IMPLEMENTATION_REVISION != EXPECTED_REVISION:
        raise ValueError("E5-B Final A1 identity mismatch")
    templates = rawls24_templates(root)
    static = {
        "Water": {"c_Q": 0.6477, "h_times_tau": 0.0, "a": 1.0},
        "Seasonal Influenza Vaccine": {"c_Q": 13.916, "h_times_tau": 0.5, "a": 1.0},
        "Crackers": {"c_Q": 0.09372, "h_times_tau": 0.0, "a": 0.9},
    }
    rebuilt = []
    for expected, seed in zip(identity["replicates"], SEEDS, strict=True):
        generated = generate_e5b(seed, templates)
        master = generated["master_500"]
        budget = benchmark_budget(master, static)
        actual = {
            "seed": seed, "parameter_row_id": generated["parameter_row_id"],
            "master_500_sha256": canonical_sha256(master),
            "prefix_sha256": {str(size): canonical_sha256(master[:size]) for size in SIZES},
            "B_r_bench": budget, "B_r_bench_sha256": canonical_sha256(budget),
        }
        if actual != expected:
            raise ValueError(f"E5-B frozen replicate identity mismatch: {seed}")
        rebuilt.append(actual)
    return {
        "status": "PASS", "generator_identity": E5B_GENERATOR_IDENTITY,
        "generator_sha256": EXPECTED_GENERATOR_SHA256, "rng_identity": RNG_IDENTITY,
        "seeds": list(SEEDS), "scenario_sizes": list(SIZES), "replicates": rebuilt,
        "parameter_row_ids": [row["parameter_row_id"] for row in rebuilt],
        "items": 3, "unique_instances": 120, "timing_repetitions": 3,
        "A0_identity": A0_IDENTITY, "A1_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION, "memory_present": False,
        "A0_timed_runs": 360, "A1_timed_runs": 360,
        "budget_rule": "ONE_B_REF_FROM_FULL500_SHARED_ACROSS_50_100_200_500",
        "nested_prefixes_verified": True,
        "timing_boundary": inherited["timing_boundary"], "execution_order": inherited["execution_order"],
        "tie_rule": inherited["tie_rule"], "E5A_hash_inventory_sha256": e5a_hash,
        "frozen_hashes": frozen_hashes(root), "E5C_runs": 0,
    }


def generated_replicate(root: Path, seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("unknown E5-B seed")
    return generate_e5b(seed, rawls24_templates(root))


def data_for_instance(
    root: Path, generated: Mapping[str, Any], sample: Mapping[str, Any], size: int, budget: float,
) -> QFRData:
    if size not in SIZES:
        raise ValueError("invalid E5-B scenario size")
    base, _ = load_base_fixture(root)
    scenarios = list(generated["master_500"][:size])
    payload = deepcopy(base)
    payload["scenarios"] = [row["scenario_id"] for row in scenarios]
    payload["demand"] = {row["scenario_id"]: deepcopy(row["demand"]) for row in scenarios}
    payload["budget"] = float(budget)
    payload["reservation_cost"] = {item: float(sample["phi"])*float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["exercise_cost"] = {item: float(sample["psi"])*float(payload["q_unit_cost"][item]) for item in ITEMS}
    payload["reliability_cost"] = {item: {"0": 0.0, "1": float(sample["c_R1_ratio"])*float(payload["q_unit_cost"][item]), "2": float(sample["c_R2_ratio"])*float(payload["q_unit_cost"][item])} for item in ITEMS}
    payload["reliability_mitigation"] = {item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])} for item in ITEMS}
    payload["q_availability"] = {}
    payload["disruption"] = {}
    for row in scenarios:
        sid, category = row["scenario_id"], int(row["category"])
        payload["q_availability"][sid] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][sid] = dict.fromkeys(ITEMS, 1.0-float(sample[f"rho_F{category}"]))
    return QFRData.from_dict(payload)


def sample_by_id(root: Path, row_id: int) -> dict[str, Any]:
    rows = load_samples(root)
    return deepcopy(rows[row_id-1])


def recovery_counts(result: Mapping[str, Any]) -> dict[str, int]:
    messages: list[str] = []
    for trace in result.get("trace", []):
        oracles = []
        if isinstance(trace.get("oracle"), Mapping): oracles.append(trace["oracle"])
        if isinstance(trace.get("full_exact_certification"), Mapping): oracles.append(trace["full_exact_certification"])
        candidate = trace.get("candidate")
        for row in candidate.get("evaluations", []) if isinstance(candidate, Mapping) else []:
            messages.append(str(row.get("solver", {}).get("message", "")))
        for oracle in oracles:
            for row in oracle.get("results", []): messages.append(str(row.get("solver", {}).get("message", "")))
    return {
        "scaled_retry_count": sum("SCALED_RETRY" in message for message in messages),
        "witness_gated_retry_count": sum("WITNESS_GATED" in message for message in messages),
    }


def verify_timing_population(rows: Sequence[Mapping[str, Any]]) -> None:
    if len(rows) != 720:
        raise ValueError("E5-B raw timing population is not 720")
    keys = [(r["replicate_id"], r["scenario_size"], r["algorithm"], r["repetition"]) for r in rows]
    if len(keys) != len(set(keys)) or any(r["certificate_status"] != "PASS" for r in rows):
        raise ValueError("E5-B timing identity/certification failure")
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows: groups.setdefault((str(row["replicate_id"]),str(row["scenario_size"]),str(row["algorithm"])),[]).append(row)
    if len(groups) != 240 or any(len(group) != 3 for group in groups.values()):
        raise ValueError("E5-B repetition coverage mismatch")
    from robust_budget_allocation.formal.e5a import _close
    for group in groups.values():
        anchor=group[0]
        for row in group[1:]:
            if not _close(float(anchor["objective"]),float(row["objective"])) or not _close(float(anchor["worst_loss"]),float(row["worst_loss"])):
                raise ValueError("E5-B repeated scientific value mismatch")


def growth_distribution(values: Sequence[float]) -> dict[str, float]:
    ordered=sorted(map(float,values))
    def q(p: float) -> float:
        at=(len(ordered)-1)*p; lo,hi=math.floor(at),math.ceil(at)
        return ordered[lo] if lo==hi else ordered[lo]+(at-lo)*(ordered[hi]-ordered[lo])
    return {"min":ordered[0],"Q25":q(.25),"median":q(.5),"geometric_mean":math.exp(sum(math.log(v) for v in ordered)/len(ordered)),"Q75":q(.75),"P90":q(.9),"P95":q(.95),"max":ordered[-1]}
