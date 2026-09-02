"""Build the temporary Rawls24 state-based F/R availability diagnostic."""

from __future__ import annotations

import csv
from copy import deepcopy
from decimal import Decimal, getcontext
import json
import math
from pathlib import Path
from typing import Any

import pyomo.environ as pyo

from robust_budget_allocation.algorithms.qfr_builders import build_qfr_extensive_form
from robust_budget_allocation.data.qfr_data import QFRData, RELIABILITY_LEVELS
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


ITEMS = ("Water", "Seasonal Influenza Vaccine", "Crackers")
MODELS = ("M0", "M1", "M2")
BUDGET_RATIOS = (0.75, 1.0, 1.25)
GROUPS = ("Florida_Major", "Florida_Minor", "NonFlorida_Major", "NonFlorida_Minor")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _close(actual: float, expected: float, label: str, tolerance: float = 1e-11) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def maximum_entropy_group_weights() -> dict[str, Decimal]:
    """Return the unique max-entropy group-constant weights at high precision."""

    getcontext().prec = 60
    florida = Decimal(2) / Decimal(5)
    major = Decimal("0.4444444444")
    residual = Decimal(1) - florida - major
    # Per-event max-entropy first-order condition: p_FM*p_Nm=p_Fm*p_NM.
    a = Decimal(67)
    b = -(Decimal(72) * (florida + major) + Decimal(5) * residual)
    c = Decimal(72) * florida * major
    fm_mass = (-b - (b * b - Decimal(4) * a * c).sqrt()) / (Decimal(2) * a)
    return {
        "Florida_Major": fm_mass / Decimal(12),
        "Florida_Minor": florida - fm_mass,
        "NonFlorida_Major": (major - fm_mass) / Decimal(5),
        "NonFlorida_Minor": (residual + fm_mass) / Decimal(6),
    }


def build_authority(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    paths = {
        "config": root / "configs/qfr24_state_availability_diagnostic_v1.json",
        "input": root / "data/r6_rawls24/unified_hurricane_input.csv",
        "demand": root / "data/r6_rawls24/unified_rawls_demand.csv",
        "manifest": root / "data/r6_rawls24/provenance_manifest.json",
        "formal": root / "configs/r6c_formal_ready_data_v2.json",
    }
    config, manifest, formal = _json(paths["config"]), _json(paths["manifest"]), _json(paths["formal"])
    inputs, raw_demands = _csv(paths["input"]), _csv(paths["demand"])
    if config["dataset_identity"] != manifest["dataset_identity"]:
        raise ValueError("Rawls24 dataset identity mismatch")
    if len(inputs) != 24 or len(raw_demands) != 24:
        raise ValueError("exactly 24 scenarios required")
    qfr = formal["qfr_data"]
    parameters = formal["parameters"]
    if tuple(qfr["items"]) != ITEMS:
        raise ValueError("commodity identity changed")
    _close(parameters["reservation_cost"]["Water"] / parameters["q_unit_cost"]["Water"], 0.2, "phi")
    _close(parameters["exercise_cost"]["Water"] / parameters["q_unit_cost"]["Water"], 0.85, "psi")
    if parameters["reliability_cost_ratios"] != [0.0, 0.1, 0.25]:
        raise ValueError("reliability premiums changed")
    if parameters["shortage_beta"] != 4.0:
        raise ValueError("shortage beta changed")

    by_id = {row["scenario_id"]: row for row in inputs}
    raw_by_id = {row["scenario_id"]: row for row in raw_demands}
    scenario_ids = tuple(row["scenario_id"] for row in inputs)
    if scenario_ids != tuple(f"h{i:02d}" for i in range(1, 25)) or scenario_ids != tuple(raw_by_id):
        raise ValueError("scenario identity/order mismatch")
    names = {row["hurricane_name"] for row in inputs}
    group_members = config["weight_groups"]
    if tuple(group_members) != GROUPS or set().union(*(set(group_members[g]) for g in GROUPS)) != names:
        raise ValueError("weight-group coverage mismatch")
    if sum(len(group_members[g]) for g in GROUPS) != 24:
        raise ValueError("weight groups overlap")
    state_members = config["state_membership"]
    if state_members["Low"] or set(state_members["Medium"]) | set(state_members["High"]) != names:
        raise ValueError("disruption-state coverage mismatch")
    if set(state_members["Medium"]) & set(state_members["High"]):
        raise ValueError("disruption states overlap")

    group_decimal = maximum_entropy_group_weights()
    name_group = {name: group for group in GROUPS for name in group_members[group]}
    name_state = {name: state for state in ("Medium", "High") for name in state_members[state]}
    scenario_weights_decimal = {
        sid: group_decimal[name_group[by_id[sid]["hurricane_name"]]] for sid in scenario_ids
    }
    decimal_total = sum(scenario_weights_decimal.values(), Decimal(0))
    if abs(decimal_total - Decimal(1)) > Decimal("1e-58"):
        raise ValueError("high-precision weight sum is not one")
    scenario_weights = {sid: float(value) for sid, value in scenario_weights_decimal.items()}
    _close(math.fsum(scenario_weights.values()), 1.0, "weight sum", 1e-15)
    florida = math.fsum(scenario_weights[sid] for sid in scenario_ids if name_group[by_id[sid]["hurricane_name"]].startswith("Florida"))
    major = math.fsum(scenario_weights[sid] for sid in scenario_ids if name_group[by_id[sid]["hurricane_name"]].endswith("Major"))
    _close(florida, 0.4, "Florida mass", 1e-15)
    _close(major, 0.4444444444, "major mass", 1e-15)

    demand: dict[str, dict[str, float]] = {}
    q_availability: dict[str, dict[str, float]] = {}
    direct_f: dict[str, dict[int, float]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    q_schedule = [float(v) for v in config["q_availability_cat1_to_cat5"]]
    availability = config["availability_by_state"]
    for sid in scenario_ids:
        source, raw = by_id[sid], raw_by_id[sid]
        name, category = source["hurricane_name"], int(source["category"])
        demand[sid] = {
            "Water": float(raw["water_unified"]),
            "Seasonal Influenza Vaccine": (140.0 / 13.916) * float(raw["medical_unified"]),
            "Crackers": 14.0 * float(raw["food_unified"]),
        }
        q_availability[sid] = dict.fromkeys(ITEMS, q_schedule[category - 1])
        direct_f[sid] = {level: float(availability[name_state[name]][f"R{level}"]) for level in RELIABILITY_LEVELS}
        metadata[sid] = {"hurricane_name": name, "year": int(source["year"]), "category": category, "state": name_state[name]}

    fbar = {item: max(demand[sid][item] for sid in scenario_ids) for item in ITEMS}
    dref = {
        item: float(sum(
            scenario_weights_decimal[sid] * Decimal(str(demand[sid][item]))
            for sid in scenario_ids
        ))
        for item in ITEMS
    }
    q_cost = {item: float(qfr["q_unit_cost"][item]) for item in ITEMS}
    horizon = {item: float(parameters["storage_horizon_cost"][item]) for item in ITEMS}
    retention = {item: float(qfr["retention"][item]) for item in ITEMS}
    budget_components = {item: (q_cost[item] + horizon[item]) * dref[item] / retention[item] for item in ITEMS}
    b_ref = math.fsum(budget_components.values())

    payload = deepcopy(qfr)
    payload.update({
        "scenarios": list(scenario_ids), "budget": b_ref, "flexible_capacity": fbar,
        "demand": demand, "q_availability": q_availability,
        # Required legacy schema fields are inert in the diagnostic builder.
        "disruption": {sid: dict.fromkeys(ITEMS, 0.0) for sid in scenario_ids},
    })
    data = QFRData.from_dict(payload)
    authority = {
        "scope": config["scope"], "scientific_status": config["scientific_status"],
        "source_files": {path.relative_to(root).as_posix(): sha256_file(path) for path in paths.values()},
        "scenario_ids": list(scenario_ids), "metadata": metadata,
        "scenario_weights": scenario_weights,
        "scenario_weights_decimal": {sid: str(value) for sid, value in scenario_weights_decimal.items()},
        "group_weights_decimal": {group: str(group_decimal[group]) for group in GROUPS},
        "weight_checks": {"total": math.fsum(scenario_weights.values()), "Florida": florida, "Major": major, "Minor": 1.0 - major},
        "weight_checks_decimal": {
            "total": str(decimal_total),
            "Florida": "0.4000000000", "Major": "0.4444444444", "Minor": "0.5555555556",
        },
        "reference_weight_role": config["reference_weight_role"],
        "D_ref": dref, "B_ref_components": budget_components, "B_ref": b_ref,
        "budget_ratios": list(BUDGET_RATIOS), "models": list(MODELS), "F_bar": fbar,
        "direct_f_availability": {sid: {str(k): v for k, v in levels.items()} for sid, levels in direct_f.items()},
        "base_qfr_data": data.to_dict(),
    }
    authority["authority_sha256"] = canonical_json_sha256(authority)
    return authority


def case_data(authority: dict[str, Any], ratio: float) -> QFRData:
    if float(ratio) not in BUDGET_RATIOS:
        raise ValueError("unregistered budget ratio")
    payload = deepcopy(authority["base_qfr_data"])
    payload["budget"] = float(authority["B_ref"]) * float(ratio)
    return QFRData.from_dict(payload)


def build_diagnostic_ef(data: QFRData, model_kind: str, direct_f: dict[str, dict[str, float]]):
    """Reuse the reviewed EF, replacing only its F availability expression."""

    model = build_qfr_extensive_form(data, model_kind)
    if model_kind == "M0":
        return model
    model.del_component(model.exercise_limit)
    model.del_component(model.fulfillable_F)
    model.del_component(model.rho)
    model.rho = pyo.Expression(
        model.I, model.Omega, model.R,
        rule=lambda _m, _i, scenario, level: float(direct_f[scenario][str(level)]),
    )
    model.fulfillable_F = pyo.Expression(
        model.I, model.Omega,
        rule=lambda m, item, scenario: sum(m.rho[item, scenario, level] * m.F[item, level] for level in m.R),
    )
    model.exercise_limit = pyo.Constraint(
        model.I, model.Omega,
        rule=lambda m, item, scenario: m.x[item, scenario] <= m.fulfillable_F[item, scenario],
    )
    model._diagnostic_direct_f_availability = True
    return model
