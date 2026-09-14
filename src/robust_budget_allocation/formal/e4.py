"""Formal E4 out-of-sample robustness support over frozen E1 evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
import csv
import json
import math
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
import pyomo.environ as pyo

from robust_budget_allocation.algorithms.qfr_exact_oracle import solve_exact_recourse
from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
    solve_qfr_final_a1,
)
from robust_budget_allocation.algorithms.qfr_numerical_validation import (
    VALIDATION_ABSOLUTE_TOLERANCE,
    family_violation_is_acceptable,
)
from robust_budget_allocation.algorithms.qfr_protocol import require_close, solve_exact, static_data_sha256
from robust_budget_allocation.algorithms.qfr_state import QFRFirstStage, first_stage_cost, validate_first_stage
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import (
    BUDGET,
    ITEMS,
    OUTPUT_ITEMS,
    POLICIES,
    POLICY_TOLERANCE,
    SAMPLE_SHA256,
    classify_policy,
    csv_bytes,
    distribution,
    load_base_fixture,
    load_samples,
    read_csv,
)
from robust_budget_allocation.formal.e2d_audit import verify_hash_inventory
from robust_budget_allocation.formal.final_design import (
    E4_GENERATOR_IDENTITY,
    RNG_IDENTITY,
    canonical_sha256,
    generate_e4b,
    select_space_filling,
    selection_identity,
)
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


EXPECTED_S200 = "2b7d7a92c9a0301203a6b73a349a32903b83434038dc88a52fe1cc734ffad32d"
EXPECTED_S100 = "1ad7dcbf17a2339a41723bea60ad0e7e8fce70017d54c5c1f80ba7412accd0ee"
EXPECTED_E4B_GENERATOR = "d39afab714dc68392db574f6efebfe0176de169b571db0a4eb471cd45afe8340"
EXPECTED_REVISION = "A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY"
E4B_SEEDS = tuple(range(20260904, 20260914))
OUTPUT = Path("formal_results/e4_final")
DESIGN = Path("configs/final_formal_scientific_design_v1.json")
MACHINE = Path("docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json")
E1_RESULTS = Path("formal_results/e1_final/e1_scientific_results.csv")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rawls24_templates(root: Path) -> list[dict[str, Any]]:
    rows = read_csv(root / "data/r6_rawls24/unified_rawls_demand.csv")
    return [{
        "scenario_id": row["scenario_id"],
        "category": int(row["category"]),
        "demand": {
            "Water": float(row["water_unified"]),
            "Seasonal Influenza Vaccine": float(row["medical_unified"]) * 10.0603621730382,
            "Crackers": float(row["food_unified"]) * 14.0,
        },
    } for row in rows]


def frozen_hashes(root: Path) -> dict[str, str]:
    directories = (
        "formal_results/e1_final",
        "formal_results/e2_final/e2a",
        "formal_results/e2_final/e2b",
        "formal_results/e2_final/e2c",
        "formal_results/e2_final/e2d",
        "formal_results/e2_final/e2d_audit",
        "formal_results/e3_final",
        "formal_results/e3_final/e3a",
        "formal_results/e3_final/e3b",
    )
    hashes: dict[str, str] = {}
    for relative in directories:
        directory = root / relative
        verify_hash_inventory(directory)
        hashes[relative] = sha256_file(directory / "HASHES.sha256")
    return hashes


def preflight(root: Path) -> dict[str, Any]:
    design = _load_json(root / DESIGN)
    machine = _load_json(root / MACHINE)
    common, e1, e4 = design["common"], design["E1"], design["E4"]
    if common["dataset"] != "rawls_24_real_single_hurricane_data_recalibration_v1":
        raise ValueError("Rawls24 dataset identity mismatch")
    if common["scenario_order"] != [f"h{i:02d}" for i in range(1, 25)]:
        raise ValueError("Rawls24 scenario order mismatch")
    if common["commodities"] != list(ITEMS) or common["model"] != "M2":
        raise ValueError("Formal model or commodity identity mismatch")
    if float(common["B_ref_E1"]) != BUDGET or float(common["beta"]) != 4.0:
        raise ValueError("Formal E4 baseline mismatch")
    if common["lambda"] != [1.0, 1.0, 1.0] or float(common["gamma_D"]) != 1.0:
        raise ValueError("Formal shortage valuation identity mismatch")
    if e1["sample_table_sha256"] != SAMPLE_SHA256 or int(e1["seed"]) != 20260903:
        raise ValueError("Frozen E1 sample identity mismatch")
    if FINAL_A1_IDENTITY != "A1_FINAL_NO_MEMORY_V1" or FINAL_A1_IMPLEMENTATION_REVISION != EXPECTED_REVISION:
        raise ValueError("Final A1 identity mismatch")
    samples = load_samples(root)
    rebuilt_s200 = select_space_filling(samples, e1["bounds"], 200)
    by_id = {int(row["sample_index"]): row for row in samples}
    rebuilt_s100 = select_space_filling([by_id[index] for index in rebuilt_s200], e1["bounds"], 100)
    s200 = selection_identity(rebuilt_s200, SAMPLE_SHA256, "E3_E4A_SHARED_S200")
    s100 = selection_identity(rebuilt_s100, SAMPLE_SHA256, "E4B_NESTED_WITHIN_S200", s200["selection_sha256"])
    if s200 != machine["S_200"] or s200["selection_sha256"] != EXPECTED_S200:
        raise ValueError("S200 identity mismatch")
    if s100 != machine["S_100"] or s100["selection_sha256"] != EXPECTED_S100:
        raise ValueError("S100 identity mismatch")
    generator = machine["E4B"]
    if generator["identity"] != E4_GENERATOR_IDENTITY or generator["generator_sha256"] != EXPECTED_E4B_GENERATOR:
        raise ValueError("E4-B generator identity mismatch")
    if generator["rng"] != RNG_IDENTITY or tuple(generator["seeds"]) != E4B_SEEDS:
        raise ValueError("E4-B RNG or seed mismatch")
    if generator["scenarios_per_seed"] != 2000 or generator["no_hurricane"] != "DISABLED":
        raise ValueError("E4-B scenario count/no-hurricane mismatch")
    if generator["scenario_draw_order"] != ["template_id", "m_common", "Water_m_item", "Vaccine_m_item", "Crackers_m_item"]:
        raise ValueError("E4-B draw order mismatch")
    templates = rawls24_templates(root)
    for seed in E4B_SEEDS:
        generated = generate_e4b(seed, templates)
        if canonical_sha256(generated) != generator["seed_table_sha256"][str(seed)]:
            raise ValueError(f"E4-B generated scenario hash mismatch: {seed}")
    if e4["A"] != {
        "name": "Historical LOHO", "parameter_subset_size": 200, "folds": 24,
        "training_scenarios_per_fold": 23, "training_optimizations": 4800,
        "budget": BUDGET, "recompute_budget": False,
    }:
        raise ValueError("E4-A frozen design mismatch")
    e1_rows = read_csv(root / E1_RESULTS)
    if len(e1_rows) != 1000 or any(row["certificate_status"] != "PASS" for row in e1_rows):
        raise ValueError("Frozen E1 evidence is incomplete")
    return {
        "status": "PASS",
        "base_commit": _git(root, "rev-parse", "HEAD"),
        "base_tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "sample_sha256": SAMPLE_SHA256,
        "S200_sha256": EXPECTED_S200,
        "S100_sha256": EXPECTED_S100,
        "S200_ids": rebuilt_s200,
        "S100_ids": rebuilt_s100,
        "generator_identity": E4_GENERATOR_IDENTITY,
        "generator_sha256": EXPECTED_E4B_GENERATOR,
        "seed_table_sha256": generator["seed_table_sha256"],
        "seeds": list(E4B_SEEDS),
        "scenarios_per_seed": 2000,
        "E4A_planned": 4800,
        "E4B_policy_seed_evaluations": 1000,
        "E4B_scenario_evaluations": 2_000_000,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "frozen_hashes": frozen_hashes(root),
        "E5_runs": 0,
    }


def data_payload_for_sample(
    base: Mapping[str, Any], metadata: Mapping[str, Mapping[str, Any]], sample: Mapping[str, Any]
) -> dict[str, Any]:
    payload = deepcopy(dict(base))
    payload["budget"] = BUDGET
    payload["reservation_cost"] = {
        item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["exercise_cost"] = {
        item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["reliability_cost"] = {
        item: {
            "0": 0.0,
            "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]),
            "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item]),
        } for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])}
        for item in ITEMS
    }
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        payload["q_availability"][scenario] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][scenario] = dict.fromkeys(ITEMS, 1.0 - float(sample[f"rho_F{category}"]))
    return payload


def subset_payload(payload: Mapping[str, Any], scenarios: Sequence[str]) -> dict[str, Any]:
    selected = tuple(scenarios)
    result = deepcopy(dict(payload))
    result["scenarios"] = list(selected)
    for name in ("demand", "q_availability", "disruption"):
        result[name] = {scenario: deepcopy(payload[name][scenario]) for scenario in selected}
    return result


def rebind_decision(decision: QFRFirstStage, data: QFRData) -> QFRFirstStage:
    rebound = QFRFirstStage(
        model_kind=decision.model_kind,
        reliability_levels=decision.reliability_levels,
        data_sha256=data.data_sha256,
        scenario_sha256=data.scenario_sha256,
        static_data_sha256=static_data_sha256(data),
        q=deepcopy(decision.q),
        f=deepcopy(decision.f),
        z=deepcopy(decision.z),
    )
    validate_first_stage(data, rebound)
    return rebound


def policy_sha256(decision: QFRFirstStage) -> str:
    """Hash scientific Q/F/R values independently of the bound scenario data."""
    return canonical_json_sha256({
        "model_kind": decision.model_kind,
        "reliability_levels": list(decision.reliability_levels),
        "q": decision.q,
        "f": decision.f,
        "z": decision.z,
    })


def decision_from_e1_row(data: QFRData, row: Mapping[str, Any]) -> QFRFirstStage:
    q, f, z = {}, {}, {}
    for item, label in OUTPUT_ITEMS.items():
        q[item] = float(row[f"Q_{label}"])
        z[item] = {level: int(row[f"z_R{level}_{label}"]) for level in range(3)}
        total_f = float(row[f"F_{label}"])
        f[item] = {level: total_f if z[item][level] else 0.0 for level in range(3)}
    decision = QFRFirstStage(
        model_kind="M2",
        reliability_levels=(0, 1, 2),
        data_sha256=data.data_sha256,
        scenario_sha256=data.scenario_sha256,
        static_data_sha256=static_data_sha256(data),
        q=q,
        f=f,
        z=z,
    )
    validate_first_stage(data, decision)
    # The promoted E1 schema deliberately retains canonical aggregate F and z,
    # but not inactive-level floating-point residues from the historical solver
    # object.  Therefore its historical object hash is provenance, not a
    # reconstructible evaluation identity.  Fail closed on every scientific
    # quantity that *is* promoted instead.
    require_close(first_stage_cost(data, decision), float(row["first_stage_cost"]), "E1 first-stage cost")
    if classify_policy(decision.to_dict()) != row["policy_label"]:
        raise ValueError(f"frozen E1 policy reconstruction mismatch: {row['simulation_id']}")
    for item, label in OUTPUT_ITEMS.items():
        if reliability_label(decision, item) != row[f"R_{label}"]:
            raise ValueError(f"frozen E1 reliability reconstruction mismatch: {row['simulation_id']}/{label}")
    return decision


def reliability_label(decision: QFRFirstStage, item: str) -> str:
    if sum(decision.f[item].values()) <= POLICY_TOLERANCE:
        return "NONE"
    selected = [level for level, value in decision.z[item].items() if value == 1]
    if len(selected) != 1:
        raise ValueError("active F lacks exactly one reliability level")
    return f"R{selected[0]}"


def serialize_loho_training(
    heldout: str,
    sample: Mapping[str, Any],
    data: QFRData,
    result: Mapping[str, Any],
) -> tuple[dict[str, Any], QFRFirstStage | None]:
    row: dict[str, Any] = {
        "heldout_scenario": heldout,
        "simulation_id": sample["simulation_id"],
        "sample_index": int(sample["sample_index"]),
        "input_sha256": sample["input_sha256"],
        "training_scenario_count": 23,
        "budget": BUDGET,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "status": result["status"],
        "certificate_status": "PASS" if result["status"] == "certified" else "FAIL",
        "iterations": result["iterations"],
        "full_exact_certification_calls": result["full_exact_certification_calls"],
        "result_sha256": result["result_sha256"],
    }
    if result["status"] != "certified":
        row.update(failure_type=result["status"], failure_message=result.get("diagnostic") or "")
        row["row_sha256"] = canonical_json_sha256(row)
        return row, None
    incumbent = result["incumbent"]
    decision = QFRFirstStage.from_dict(incumbent["first_stage"])
    oracle = incumbent["oracle"]
    pre = first_stage_cost(data, decision)
    row.update(
        failure_type="", failure_message="",
        first_stage_sha256=decision.sha256,
        policy_sha256=policy_sha256(decision),
        policy_label=classify_policy(decision.to_dict()),
        training_T_COST=float(result["objective"]),
        training_worst_scenario=oracle["worst_scenario"],
        training_worst_loss=float(oracle["worst_loss"]),
        first_stage_cost=float(pre),
    )
    for item, label in OUTPUT_ITEMS.items():
        row[f"Q_{label}"] = float(decision.q[item])
        row[f"F_{label}"] = float(sum(decision.f[item].values()))
        row[f"R_{label}"] = reliability_label(decision, item)
    row["row_sha256"] = canonical_json_sha256(row)
    return row, decision


def heldout_row(
    heldout: str,
    sample: Mapping[str, Any],
    singleton: QFRData,
    loho_decision: QFRFirstStage,
    full_decision: QFRFirstStage,
) -> dict[str, Any]:
    loho = solve_exact_recourse(singleton, rebind_decision(loho_decision, singleton), heldout)
    full = solve_exact_recourse(singleton, rebind_decision(full_decision, singleton), heldout)
    if loho["solver"]["status"] != "optimal" or full["solver"]["status"] != "optimal":
        raise RuntimeError(f"held-out exact recourse failure: {heldout}/{sample['simulation_id']}")
    loho_pre = first_stage_cost(singleton, rebind_decision(loho_decision, singleton))
    full_pre = first_stage_cost(singleton, rebind_decision(full_decision, singleton))
    row: dict[str, Any] = {
        "heldout_scenario": heldout,
        "simulation_id": sample["simulation_id"],
        "sample_index": int(sample["sample_index"]),
        "loho_first_stage_sha256": loho_decision.sha256,
        "full24_first_stage_sha256": full_decision.sha256,
        "loho_policy_sha256": policy_sha256(loho_decision),
        "full24_policy_sha256": policy_sha256(full_decision),
        "loho_heldout_recourse_sha256": canonical_json_sha256(loho),
        "full24_heldout_recourse_sha256": canonical_json_sha256(full),
        "heldout_emergency_expenditure": float(loho["exercise_cost"]),
        "heldout_shortage_loss": float(loho["shortage_loss"]),
        "heldout_total_cost": float(loho_pre + loho["loss"]),
        "full24_policy_heldout_total_cost": float(full_pre + full["loss"]),
        "heldout_policy_regret_vs_full24": float((loho_pre + loho["loss"]) - (full_pre + full["loss"])),
    }
    for item, label in OUTPUT_ITEMS.items():
        row[f"heldout_exercise_{label}"] = float(loho["exercise"][item])
        row[f"heldout_shortage_{label}"] = float(loho["shortage"][item])
    total_demand = sum(float(singleton.demand[heldout][item]) for item in ITEMS)
    total_shortage = sum(float(loho["shortage"][item]) for item in ITEMS)
    row["heldout_raw_total_shortage"] = total_shortage
    row["heldout_service_level_cross_unit_descriptive"] = 1.0 - total_shortage / total_demand
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def oos_payload(
    base_payload: Mapping[str, Any],
    sample: Mapping[str, Any],
    scenarios: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = deepcopy(dict(base_payload))
    ids = [str(row["scenario_id"]) for row in scenarios]
    payload["scenarios"] = ids
    payload["budget"] = BUDGET
    payload["reservation_cost"] = {
        item: float(sample["phi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["exercise_cost"] = {
        item: float(sample["psi"]) * float(payload["q_unit_cost"][item]) for item in ITEMS
    }
    payload["reliability_cost"] = {
        item: {"0": 0.0, "1": float(sample["c_R1_ratio"]) * float(payload["q_unit_cost"][item]), "2": float(sample["c_R2_ratio"]) * float(payload["q_unit_cost"][item])}
        for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])} for item in ITEMS
    }
    payload["demand"] = {str(row["scenario_id"]): deepcopy(row["demand"]) for row in scenarios}
    payload["q_availability"] = {}
    payload["disruption"] = {}
    for row in scenarios:
        scenario, category = str(row["scenario_id"]), int(row["category"])
        payload["q_availability"][scenario] = dict.fromkeys(ITEMS, float(sample[f"rho_Q{category}"]))
        payload["disruption"][scenario] = dict.fromkeys(ITEMS, 1.0 - float(sample[f"rho_F{category}"]))
    return payload


def _available_q(data: QFRData, decision: QFRFirstStage, item: str, scenario: str) -> float:
    return data.retention[item] * data.q_availability[scenario][item] * decision.q[item]


def _fulfillable(data: QFRData, decision: QFRFirstStage, item: str, scenario: str) -> float:
    return sum((1.0 - (1.0 - data.reliability_mitigation[item][level]) * data.disruption[scenario][item]) * decision.f[item][level] for level in decision.reliability_levels)


def _batch_witness_feasible(data: QFRData, decision: QFRFirstStage) -> bool:
    """Prove batch feasibility with x=0 and shortage covering unmet demand."""
    pre = validate_first_stage(data, decision)
    if not family_violation_is_acceptable("budget", pre - data.budget, data.budget, pre, 0.0):
        return False
    for scenario in data.scenarios:
        for item in data.items:
            available = _available_q(data, decision, item, scenario)
            shortage = max(0.0, data.demand[scenario][item] - available)
            flow = data.demand[scenario][item] - available - shortage
            if not family_violation_is_acceptable(
                "quantity_flow", flow, data.demand[scenario][item], available, shortage
            ):
                return False
    return True


def _solve_scaled_oos_batch(
    model: pyo.ConcreteModel, data: QFRData, decision: QFRFirstStage
):
    """Solve an algebraically equivalent scaled clone and map it back."""
    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    objective_reference = 0.0
    for scenario in data.scenarios:
        for item in data.items:
            quantity = max(
                1.0,
                abs(data.demand[scenario][item]),
                abs(_available_q(data, decision, item, scenario)),
                abs(_fulfillable(data, decision, item, scenario)),
            )
            model.scaling_factor[model.x[scenario, item]] = 1.0 / quantity
            model.scaling_factor[model.u[scenario, item]] = 1.0 / quantity
            model.scaling_factor[model.balance[scenario, item]] = 1.0 / quantity
            model.scaling_factor[model.exercise_limit[scenario, item]] = 1.0 / quantity
            objective_reference += max(
                data.exercise_cost[item], data.shortage_cost[item]
            ) * data.demand[scenario][item]
        model.scaling_factor[model.budget[scenario]] = 1.0 / max(1.0, abs(data.budget))
    objective_factor = 1.0 / max(1.0, objective_reference)
    model.scaling_factor[model.total_cost] = objective_factor
    transformation = pyo.TransformationFactory("core.scale_model")
    scaled_model = transformation.create_using(model, rename=False)
    outcome = solve_exact(scaled_model)
    if outcome.status != "optimal":
        return outcome
    transformation.propagate_solution(scaled_model, model)
    return replace(
        outcome,
        objective=float(outcome.objective) / objective_factor,
        lower_bound=float(outcome.lower_bound) / objective_factor,
        message="E4B_BATCH_SCALED_RETRY_MAPPED_BACK_FOR_ORIGINAL_SEMANTIC_VALIDATION",
    )


def evaluate_oos_batch(data: QFRData, decision: QFRFirstStage) -> dict[str, Any]:
    """Solve 2,000 separable exact recourse LPs as one algebraically equivalent batch."""
    pre = validate_first_stage(data, decision)
    remaining = max(0.0, data.budget - min(pre, data.budget))
    model = pyo.ConcreteModel(name="Formal E4-B separable exact recourse batch")
    model.W = pyo.Set(initialize=data.scenarios, ordered=True)
    model.I = pyo.Set(initialize=data.items, ordered=True)
    model.x = pyo.Var(model.W, model.I, domain=pyo.NonNegativeReals)
    model.u = pyo.Var(model.W, model.I, domain=pyo.NonNegativeReals)
    model.exercise_limit = pyo.Constraint(model.W, model.I, rule=lambda m, w, i: m.x[w, i] <= _fulfillable(data, decision, i, w))
    model.budget = pyo.Constraint(model.W, rule=lambda m, w: sum(data.exercise_cost[i] * m.x[w, i] for i in m.I) <= remaining)
    model.balance = pyo.Constraint(model.W, model.I, rule=lambda m, w, i: _available_q(data, decision, i, w) + m.x[w, i] + m.u[w, i] >= data.demand[w][i])
    model.total_cost = pyo.Objective(expr=sum(data.exercise_cost[i] * model.x[w, i] + data.shortage_cost[i] * model.u[w, i] for w in model.W for i in model.I), sense=pyo.minimize)
    started = perf_counter()
    outcome = solve_exact(model)
    production_termination = outcome.termination
    scaled_retry_triggered = False
    if outcome.status != "optimal":
        text = " ".join(
            value for value in (outcome.solver_status, outcome.termination, outcome.message) if value
        ).lower()
        recognized_numerical = any(marker in text for marker in (
            "numerical", "solverfailure", "internal solver", "internalerror",
            "internal error", "unable to retrieve attribute",
        ))
        infeasible_with_witness = (
            outcome.termination.strip().lower() == "infeasible"
            and _batch_witness_feasible(data, decision)
        )
        if recognized_numerical or infeasible_with_witness:
            scaled_retry_triggered = True
            outcome = _solve_scaled_oos_batch(model, data, decision)
    runtime = perf_counter() - started
    if outcome.status != "optimal":
        return {
            "status": "failure", "solver": outcome.to_dict(), "runtime_seconds": runtime,
            "production_termination": production_termination,
            "scaled_retry_triggered": scaled_retry_triggered, "results": [],
        }
    rows: list[dict[str, Any]] = []
    summed_loss = 0.0
    for scenario in data.scenarios:
        exercise = {item: float(pyo.value(model.x[scenario, item])) for item in data.items}
        shortage = {item: float(pyo.value(model.u[scenario, item])) for item in data.items}
        exercise_cost = sum(data.exercise_cost[item] * exercise[item] for item in data.items)
        shortage_loss = sum(data.shortage_cost[item] * shortage[item] for item in data.items)
        loss = exercise_cost + shortage_loss
        violations = []
        for item in data.items:
            if exercise[item] < -VALIDATION_ABSOLUTE_TOLERANCE or shortage[item] < -VALIDATION_ABSOLUTE_TOLERANCE:
                raise ValueError("E4-B batch exact recourse violates nonnegativity")
            available = _available_q(data, decision, item, scenario)
            flow = data.demand[scenario][item] - available - exercise[item] - shortage[item]
            cap = exercise[item] - _fulfillable(data, decision, item, scenario)
            if not family_violation_is_acceptable("quantity_flow", flow, data.demand[scenario][item], available, exercise[item], shortage[item]):
                raise ValueError("E4-B batch exact recourse violates demand balance")
            if not family_violation_is_acceptable("fulfillment_capacity", cap, exercise[item], _fulfillable(data, decision, item, scenario)):
                raise ValueError("E4-B batch exact recourse violates fulfillment")
            violations.extend((flow, cap, -exercise[item], -shortage[item]))
        budget_violation = pre + exercise_cost - data.budget
        if not family_violation_is_acceptable("budget", budget_violation, data.budget, pre, exercise_cost):
            raise ValueError("E4-B batch exact recourse violates budget")
        total_demand = sum(data.demand[scenario][item] for item in data.items)
        total_shortage = sum(shortage.values())
        row = {
            "scenario_id": scenario,
            "exercise": exercise,
            "shortage": shortage,
            "exercise_cost": float(exercise_cost),
            "shortage_loss": float(shortage_loss),
            "recourse_loss": float(loss),
            "total_cost": float(pre + loss),
            "raw_total_shortage": float(total_shortage),
            "service_level_cross_unit_descriptive": float(1.0 - total_shortage / total_demand),
            "maximum_feasibility_violation": float(max(0.0, budget_violation, *violations)),
        }
        summed_loss += loss
        rows.append(row)
    require_close(summed_loss, float(outcome.objective), "E4-B separable batch exact objective")
    return {
        "status": "optimal",
        "solver": outcome.to_dict(),
        "runtime_seconds": runtime,
        "production_termination": production_termination,
        "scaled_retry_triggered": scaled_retry_triggered,
        "batch_equivalence": "SUM_OF_INDEPENDENT_ORIGINAL_EXACT_RECOURSE_LPS",
        "results": rows,
        "results_sha256": canonical_json_sha256(rows),
    }


def summarize_oos_batch(
    sample: Mapping[str, Any], e1_row: Mapping[str, Any], seed: int, batch: Mapping[str, Any]
) -> dict[str, Any]:
    rows = batch["results"]
    output: dict[str, Any] = {
        "simulation_id": sample["simulation_id"],
        "sample_index": int(sample["sample_index"]),
        "seed": seed,
        "policy_label": e1_row["policy_label"],
        "in_sample_robust_T_COST": float(e1_row["T_COST"]),
        "scenario_count": len(rows),
        "status": batch["status"],
        "batch_results_sha256": batch["results_sha256"],
        "solver_status": batch["solver"]["status"],
        "runtime_seconds": float(batch["runtime_seconds"]),
        "production_termination": batch["production_termination"],
        "scaled_retry_triggered": bool(batch["scaled_retry_triggered"]),
    }
    field_map = {
        "T_COST": "total_cost",
        "shortage_loss": "shortage_loss",
        "emergency_expenditure": "exercise_cost",
        "raw_total_shortage_cross_unit_descriptive": "raw_total_shortage",
        "service_level_cross_unit_descriptive": "service_level_cross_unit_descriptive",
    }
    for prefix, source in field_map.items():
        stats = distribution([float(row[source]) for row in rows])
        for name, value in stats.items():
            output[f"{prefix}_{name}"] = value
        values = sorted(float(row[source]) for row in rows)
        for label, quantile in (("P05", .05), ("P90", .90), ("P95", .95)):
            output[f"{prefix}_{label}"] = float(np.quantile(values, quantile, method="linear"))
    output["Pr_any_shortage_gt_policy_tolerance"] = sum(float(row["raw_total_shortage"]) > POLICY_TOLERANCE for row in rows) / len(rows)
    for item, label in OUTPUT_ITEMS.items():
        values = [float(row["shortage"][item]) for row in rows]
        output[f"shortage_{label}_mean"] = float(np.mean(values))
        output[f"shortage_{label}_median"] = float(np.median(values))
        output[f"shortage_{label}_max"] = float(np.max(values))
        output[f"shortage_{label}_P95"] = float(np.quantile(values, .95, method="linear"))
    output["row_sha256"] = canonical_json_sha256(output)
    return output


def aggregate_rows(rows: Sequence[Mapping[str, Any]], group_fields: Sequence[str], value_fields: Sequence[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    result = []
    for key in sorted(groups, key=lambda value: tuple(str(x) for x in value)):
        members = groups[key]
        out = {field: value for field, value in zip(group_fields, key, strict=True)}
        out["N"] = len(members)
        for field in value_fields:
            stats = distribution([float(row[field]) for row in members])
            for name, value in stats.items():
                out[f"{field}_{name}"] = value
        result.append(out)
    return result
