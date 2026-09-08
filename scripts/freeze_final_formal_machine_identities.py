"""Build/check Final Formal machine identities without running an optimizer."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from robust_budget_allocation.formal.final_design import (  # noqa: E402
    E4_GENERATOR_IDENTITY, E5B_GENERATOR_IDENTITY, E5C_GENERATOR_IDENTITY,
    QUANTILE_POLICY, RNG_IDENTITY, TIE_POLICY, benchmark_budget, canonical_sha256,
    e5c_budget, generate_e4b, generate_e5b, generate_e5c_items, select_f_supply_risk,
    select_reliability_economics, select_space_filling, selection_identity,
)
from audit_pr27_final_e1_identity import _reconstruct_samples  # noqa: E402

CONFIG_PATH = ROOT / "configs/final_formal_scientific_design_v1.json"
OUTPUT_PATH = ROOT / "docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json"
PR27_AUDIT_PATH = ROOT / "docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json"


def rawls24_templates() -> list[dict[str, object]]:
    demand_rows = list(csv.DictReader((ROOT / "data/r6_rawls24/unified_rawls_demand.csv").open(encoding="utf-8", newline="")))
    return [{
        "scenario_id": row["scenario_id"],
        "category": int(row["category"]),
        "demand": {
            "Water": float(row["water_unified"]),
            "Seasonal Influenza Vaccine": float(row["medical_unified"]) * 10.0603621730382,
            "Crackers": float(row["food_unified"]) * 14.0,
        },
    } for row in demand_rows]


def build() -> dict[str, object]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pr27_audit = json.loads(PR27_AUDIT_PATH.read_text(encoding="utf-8"))
    sample_bytes = _reconstruct_samples(config["E1"])
    if __import__("hashlib").sha256(sample_bytes).hexdigest() != config["E1"]["sample_table_sha256"]:
        raise RuntimeError("frozen E1 sample hash mismatch")
    parameter_rows = list(csv.DictReader(io.StringIO(sample_bytes.decode("utf-8"))))
    active_ids = set(pr27_audit["f_active_filter_evidence"]["row_ids"])
    scientific_rows = [{
        "sample_index": row["sample_index"],
        "F_Water": 1.0 if int(row["sample_index"]) in active_ids else 0.0,
        "F_Seasonal Influenza Vaccine": 0.0,
        "F_Crackers": 0.0,
    } for row in parameter_rows]
    bounds = config["E1"]["bounds"]
    s200 = select_space_filling(parameter_rows, bounds, 200)
    by_id = {int(row["sample_index"]): row for row in parameter_rows}
    s100 = select_space_filling([by_id[index] for index in s200], bounds, 100)
    supply = select_f_supply_risk(parameter_rows)
    reliability = select_reliability_economics(
        parameter_rows, scientific_rows, float(config["E1"]["policy_tolerance"])
    )
    templates = rawls24_templates()
    supply["selected_full_rho_F_curves"] = {
        level: [float(by_id[row_id][f"rho_F{k}"]) for k in range(1, 6)]
        for level, row_id in supply["levels"].items()
    }
    reliability["selected_actual_reliability_tuples"] = {
        level: {name: float(by_id[row_id][name]) for name in ("eta_1", "eta_2", "c_R1_ratio", "c_R2_ratio")}
        for level, row_id in reliability["levels"].items()
    }

    e4_seeds = list(range(20260904, 20260914))
    e4_seed_hashes = {}
    for seed in e4_seeds:
        scenarios = generate_e4b(seed, templates)
        e4_seed_hashes[str(seed)] = canonical_sha256(scenarios)
    e4_body = {
        "identity": E4_GENERATOR_IDENTITY, "rng": RNG_IDENTITY,
        "seeds": e4_seeds, "scenarios_per_seed": 2000,
        "scenario_draw_order": ["template_id", "m_common", "Water_m_item", "Vaccine_m_item", "Crackers_m_item"],
        "template_measure": "DISCRETE_UNIFORM_H01_H24", "no_hurricane": "DISABLED",
        "shared_scenario_tables_across_all_100_policies": True,
        "seed_table_sha256": e4_seed_hashes,
    }

    static = {
        "Water": {"c_Q": 0.6477, "h_times_tau": 0.0, "a": 1.0},
        "Seasonal Influenza Vaccine": {"c_Q": 13.916, "h_times_tau": 0.5, "a": 1.0},
        "Crackers": {"c_Q": 0.09372, "h_times_tau": 0.0, "a": 0.9},
    }
    e5b_replicates = []
    for seed in range(20261001, 20261031):
        generated = generate_e5b(seed, templates)
        master = generated["master_500"]
        budget = benchmark_budget(master, static)
        e5b_replicates.append({
            "seed": seed, "parameter_row_id": generated["parameter_row_id"],
            "master_500_sha256": canonical_sha256(master),
            "prefix_sha256": {str(size): canonical_sha256(master[:size]) for size in (50, 100, 200, 500)},
            "B_r_bench": budget, "B_r_bench_sha256": canonical_sha256(budget),
        })
    e5b_body = {
        "identity": E5B_GENERATOR_IDENTITY, "rng": RNG_IDENTITY,
        "seeds": list(range(20261001, 20261031)),
        "draw_order": ["parameter_row_id", "per_scenario:template_id", "per_scenario:m_common", "per_scenario:Water_m_item", "per_scenario:Vaccine_m_item", "per_scenario:Crackers_m_item"],
        "nested_prefix_sizes": [50, 100, 200, 500],
        "budget_formula": "sum_i((cQ_i+h_i*tau)*mean_Omega500(d_i)/a_i)",
        "replicates": e5b_replicates,
    }

    e5c_replicates = []
    for seed in range(20261101, 20261131):
        generated = generate_e5c_items(seed, templates)
        master = generated["master_9"]
        scenarios = generated["master_100"]
        e5c_replicates.append({
            "seed": seed, "parameter_row_id": generated["parameter_row_id"],
            "master_9_sha256": canonical_sha256(master),
            "master_100_scenario_sha256": canonical_sha256(scenarios),
            "prefix_sha256": {str(size): canonical_sha256(master[:size]) for size in (3, 6, 9)},
            "demand_matrix_sha256": {
                str(size): canonical_sha256([
                    {"scenario_id": row["scenario_id"], "demand": {
                        item["item_id"]: row["demand"][item["item_id"]] for item in master[:size]
                    }} for row in scenarios
                ]) for size in (3, 6, 9)
            },
            "B_ref_bench": {str(size): e5c_budget(master, scenarios, size) for size in (3, 6, 9)},
        })
    e5c_body = {
        "identity": E5C_GENERATOR_IDENTITY, "rng": RNG_IDENTITY,
        "seeds": list(range(20261101, 20261131)),
        "draw_order": ["parameter_row_id", "per_item:m_c", "per_item:m_d", "conditional:m_h_or_a", "per_scenario:template_id", "per_scenario:m_common"],
        "item_order": [f"{kind}_{index}" for index in range(1, 4) for kind in ("Standard", "Preservation", "StorageLoss")],
        "nested_prefix_sizes": [3, 6, 9], "scenario_count": 100,
        "template_measure": "DISCRETE_UNIFORM_H01_H24",
        "template_category": "INHERITED",
        "no_hurricane": "DISABLED",
        "archetype_base_demand": {"Standard": "Water", "Preservation": "Seasonal Influenza Vaccine", "StorageLoss": "Crackers"},
        "demand_formula": "template_archetype_demand*m_d_item*m_common_scenario",
        "extra_item_by_scenario_noise": False,
        "scenario_sharing": "SAME_MASTER_100_ACROSS_I3_I6_I9",
        "replicates": e5c_replicates,
    }
    s200_identity = selection_identity(s200, config["E1"]["sample_table_sha256"], "E3_E4A_SHARED_S200")
    s100_identity = selection_identity(
        s100, config["E1"]["sample_table_sha256"], "E4B_NESTED_WITHIN_S200",
        parent_selection_sha256=s200_identity["selection_sha256"],
    )
    return {
        "schema_version": 1,
        "scope": "FINAL_FORMAL_MACHINE_IDENTITIES_V1_SOLVER_FREE",
        "scientific_optimization_runs": 0,
        "source_sample_sha256": config["E1"]["sample_table_sha256"],
        "selection_policy": {"tie": TIE_POLICY, "quantile": QUANTILE_POLICY},
        "S_200": s200_identity,
        "S_100": s100_identity,
        "E3B_F_supply_risk": {**supply, "identity_sha256": canonical_sha256(supply)},
        "E3B_reliability_economics": {**reliability, "identity_sha256": canonical_sha256(reliability)},
        "E4B": {**e4_body, "generator_sha256": canonical_sha256(e4_body)},
        "E5B": {**e5b_body, "generator_sha256": canonical_sha256(e5b_body)},
        "E5C": {**e5c_body, "generator_sha256": canonical_sha256(e5c_body)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(build(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.write:
        OUTPUT_PATH.write_text(payload, encoding="utf-8", newline="\n")
    elif not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != payload:
        raise SystemExit("FINAL_FORMAL_MACHINE_IDENTITIES_v1.json is stale")
    print("FINAL FORMAL MACHINE IDENTITIES: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
