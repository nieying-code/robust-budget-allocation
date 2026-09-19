"""Independent Crackers retention x F-economics S200 supplement.

This module reuses the frozen E3-A panel, F-economics definition, final A1
implementation, and result schema.  It does not mutate or regenerate Formal
E1--E5 artifacts.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from robust_budget_allocation.algorithms.qfr_final_a1 import (
    FINAL_A1_IDENTITY,
    FINAL_A1_IMPLEMENTATION_REVISION,
    solve_qfr_final_a1,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.formal.e2a import (
    BUDGET,
    ITEMS,
    OUTPUT_ITEMS,
    POLICIES,
    POLICY_TOLERANCE,
    load_base_fixture,
    load_samples,
)
from robust_budget_allocation.formal.e2b import serialize_result as _serialize_base
from robust_budget_allocation.formal.e3 import (
    EXPECTED_S200,
    F_PAIR,
    distribution,
    preflight as e3_preflight,
    s200_samples,
)
from robust_budget_allocation.formal.e5b import recovery_counts
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file


CONFIG = Path("configs/crackers_qf_interaction_s200_v1.json")
OUTPUT = Path("simulation_results/crackers_qf_interaction_s200")
RETENTION_LEVELS = (1.0, 0.9, 0.8)
F_ECONOMICS_LEVELS = (0.8, 1.0, 1.2)
PER_CELL_N = 200


def case_id(retention: float, multiplier: float) -> str:
    return f"CQF_A{int(round(retention * 100)):03d}_MF{int(round(multiplier * 100)):03d}"


CASES = {
    case_id(retention, multiplier): {
        "a_C": retention,
        "m_F": multiplier,
        "phi": F_PAIR[multiplier][0],
        "psi": F_PAIR[multiplier][1],
    }
    for retention in RETENTION_LEVELS
    for multiplier in F_ECONOMICS_LEVELS
}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _git_object_available(root: Path, revision: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", revision],
        cwd=root,
        capture_output=True,
    ).returncode == 0


def _validate_frozen_git_identity(root: Path, config: Mapping[str, Any]) -> str:
    """Validate the immutable base without assuming that a named branch exists."""

    base_head = str(config["base_main_head"])
    base_tree = str(config["base_main_tree"])
    formal_tree = str(config["formal_results_tree"])
    if _git_object_available(root, f"{base_head}^{{commit}}"):
        if _git(root, "rev-parse", f"{base_head}^{{commit}}") != base_head:
            raise ValueError("authorized base commit identity mismatch")
        if _git(root, "rev-parse", f"{base_head}^{{tree}}") != base_tree:
            raise ValueError("authorized base tree mismatch")
        if _git(root, "rev-parse", f"{base_head}:formal_results") != formal_tree:
            raise ValueError("frozen Formal E1-E5 tree mismatch")
        return "anchored_base_commit"

    if _git(root, "rev-parse", "--is-shallow-repository") != "true":
        raise ValueError("authorized base commit is unavailable in a non-shallow repository")
    if _git(root, "rev-parse", "HEAD:formal_results") != formal_tree:
        raise ValueError("frozen Formal E1-E5 tree mismatch in shallow checkout")
    return "shallow_checkout_formal_tree"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def preflight(root: Path) -> dict[str, Any]:
    config = _load_json(root / CONFIG)
    frozen = e3_preflight(root)
    if config["scope"] != "CRACKERS_QF_INTERACTION_S200_SUPPLEMENT_V1":
        raise ValueError("supplement scope mismatch")
    if frozen["S200_sha256"] != EXPECTED_S200 != config["S200_sha256"]:
        raise ValueError("S200 identity mismatch")
    if tuple(map(float, config["retention_levels"])) != RETENTION_LEVELS:
        raise ValueError("Crackers retention grid mismatch")
    expected_f = {
        str(multiplier): {"phi": F_PAIR[multiplier][0], "psi": F_PAIR[multiplier][1]}
        for multiplier in F_ECONOMICS_LEVELS
    }
    if config["F_economics"] != expected_f:
        raise ValueError("F-economics scaling differs from frozen E3-A")
    source_hashes = {
        "source_e3a_manifest_sha256": root / "formal_results/e3_final/e3a/manifest.json",
        "source_e3a_scientific_results_sha256": root / "formal_results/e3_final/e3a/scientific_results.csv",
        "formal_design_sha256": root / "configs/final_formal_scientific_design_v1.json",
        "final_a1_source_sha256": root / "src/robust_budget_allocation/algorithms/qfr_final_a1.py",
    }
    for field, path in source_hashes.items():
        if sha256_file(path) != config[field]:
            raise ValueError(f"frozen source identity mismatch: {field}")
    git_identity_validation = _validate_frozen_git_identity(root, config)
    if FINAL_A1_IDENTITY != config["fixed"]["algorithm_identity"]:
        raise ValueError("Final A1 identity mismatch")
    if FINAL_A1_IMPLEMENTATION_REVISION != config["fixed"]["implementation_revision"]:
        raise ValueError("Final A1 implementation revision mismatch")
    samples = s200_samples(root, frozen)
    if len(samples) != PER_CELL_N or len({row["simulation_id"] for row in samples}) != PER_CELL_N:
        raise ValueError("S200 population is not unique and complete")
    return {
        "status": "PASS",
        "scope": config["scope"],
        "base_main_head": config["base_main_head"],
        "base_main_tree": config["base_main_tree"],
        "formal_results_tree": config["formal_results_tree"],
        "git_identity_validation": git_identity_validation,
        "sample_sha256": frozen["sample_sha256"],
        "S200_sha256": frozen["S200_sha256"],
        "S200_ids": frozen["S200_ids"],
        "cases": CASES,
        "per_cell_N": PER_CELL_N,
        "planned": len(CASES) * PER_CELL_N,
        "algorithm_identity": FINAL_A1_IDENTITY,
        "implementation_revision": FINAL_A1_IMPLEMENTATION_REVISION,
        "source_hashes": {field: config[field] for field in source_hashes},
        "formal_e3_frozen_hashes": frozen["frozen_hashes"],
        "resampled": False,
        "model_changed": False,
        "algorithm_changed": False,
        "tolerance_changed": False,
    }


def treated_sample(case: str, background: Mapping[str, Any]) -> dict[str, Any]:
    if case not in CASES:
        raise ValueError(f"unknown Crackers Q-F supplement case: {case}")
    sample = deepcopy(dict(background))
    sample["phi"] = CASES[case]["phi"]
    sample["psi"] = CASES[case]["psi"]
    return sample


def data_for_sample(
    base: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Any]],
    case: str,
    sample: Mapping[str, Any],
) -> QFRData:
    payload = deepcopy(dict(base))
    treatment = CASES[case]
    payload["retention"]["Crackers"] = treatment["a_C"]
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
        }
        for item in ITEMS
    }
    payload["reliability_mitigation"] = {
        item: {"0": 0.0, "1": float(sample["eta_1"]), "2": float(sample["eta_2"])}
        for item in ITEMS
    }
    for scenario in payload["scenarios"]:
        category = int(metadata[scenario]["category"])
        payload["q_availability"][scenario] = dict.fromkeys(
            ITEMS, float(sample[f"rho_Q{category}"])
        )
        payload["disruption"][scenario] = dict.fromkeys(
            ITEMS, 1.0 - float(sample[f"rho_F{category}"])
        )
    return QFRData.from_dict(payload)


def serialize(
    case: str,
    background: Mapping[str, Any],
    treated: Mapping[str, Any],
    data: QFRData,
    metadata: Mapping[str, Mapping[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    row = _serialize_base("E2B_B075", background, data, metadata, result)
    row.update(
        experiment_part="CRACKERS_QF_INTERACTION_SUPPLEMENT",
        case_id=case,
        background_simulation_id=background["simulation_id"],
        background_sample_index=background["sample_index"],
        budget_ratio=1.0,
        budget=BUDGET,
        beta=4.0,
        lambda_Water=1.0,
        lambda_Vaccine=1.0,
        lambda_Crackers=1.0,
        gamma_D=1.0,
        h_V_tau=0.5,
        a_C=CASES[case]["a_C"],
        m_F=CASES[case]["m_F"],
        phi=float(treated["phi"]),
        psi=float(treated["psi"]),
        eta_1=float(treated["eta_1"]),
        eta_2=float(treated["eta_2"]),
        c_R1_ratio=float(treated["c_R1_ratio"]),
        c_R2_ratio=float(treated["c_R2_ratio"]),
        **recovery_counts(result),
    )
    if row.get("certificate_status") == "PASS":
        for item, label in OUTPUT_ITEMS.items():
            row[f"shortage_loss_{label}"] = (
                float(data.shortage_cost[item]) * float(row[f"worst_shortage_{label}"])
            )
        row["F_total"] = sum(float(row[f"F_{label}"]) for label in OUTPUT_ITEMS.values())
        row["paid_R_any"] = any(
            row[f"R_{label}"] in {"R1", "R2"} for label in OUTPUT_ITEMS.values()
        )
        row["R1_item_count"] = sum(
            row[f"R_{label}"] == "R1" for label in OUTPUT_ITEMS.values()
        )
        row["R2_item_count"] = sum(
            row[f"R_{label}"] == "R2" for label in OUTPUT_ITEMS.values()
        )
    row.pop("row_sha256", None)
    row["row_sha256"] = canonical_json_sha256(row)
    return row


def solve_one(
    root: Path,
    case: str,
    background: Mapping[str, Any],
) -> dict[str, Any]:
    base, metadata = load_base_fixture(root)
    treated = treated_sample(case, background)
    data = data_for_sample(base, metadata, case, treated)
    result = solve_qfr_final_a1(data, "M2")
    return serialize(case, background, treated, data, metadata, result)


def _truth(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _rate(count: int, n: int) -> float:
    return round(count / n * 100.0, 12)


def _conditional_mean(values: Sequence[float]) -> float | None:
    selected = [float(value) for value in values if float(value) > POLICY_TOLERANCE]
    return sum(selected) / len(selected) if selected else None


def summarize(case: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    treatment = CASES[case]
    policy = Counter(str(row["policy_label"]) for row in rows)
    mixed = sum(_truth(row["mixed_aggregate_QF"]) for row in rows)
    same = sum(_truth(row["same_item_QF_coexistence"]) for row in rows)
    cross = sum(_truth(row["cross_item_specialization"]) for row in rows)
    out: dict[str, Any] = {
        "case_id": case,
        **treatment,
        "N": n,
        "policy_counts": {name: policy.get(name, 0) for name in POLICIES},
        "mixed_QF_count": mixed,
        "mixed_QF_rate": _rate(mixed, n),
        "same_item_QF_count": same,
        "same_item_QF_rate": _rate(same, n),
        "cross_item_QF_count": cross,
        "cross_item_QF_rate": _rate(cross, n),
        "commodities": {},
    }
    for label in OUTPUT_ITEMS.values():
        q = [float(row[f"Q_{label}"]) for row in rows]
        f = [float(row[f"F_{label}"]) for row in rows]
        q_count = sum(value > POLICY_TOLERANCE for value in q)
        f_count = sum(value > POLICY_TOLERANCE for value in f)
        out["commodities"][label] = {
            "Q_activation_count": q_count,
            "Q_activation_rate": _rate(q_count, n),
            "F_activation_count": f_count,
            "F_activation_rate": _rate(f_count, n),
            "Q": distribution(q),
            "F": distribution(f),
            "Q_conditional_mean": _conditional_mean(q),
            "F_conditional_mean": _conditional_mean(f),
        }
    paid = sum(_truth(row["paid_R_any"]) for row in rows)
    r1_cases = sum(int(row["R1_item_count"]) > 0 for row in rows)
    r2_cases = sum(int(row["R2_item_count"]) > 0 for row in rows)
    out["reliability"] = {
        "paid_R_count": paid,
        "paid_R_rate": _rate(paid, n),
        "R1_case_count": r1_cases,
        "R1_case_rate": _rate(r1_cases, n),
        "R2_case_count": r2_cases,
        "R2_case_rate": _rate(r2_cases, n),
        "R1_item_selections": sum(int(row["R1_item_count"]) for row in rows),
        "R2_item_selections": sum(int(row["R2_item_count"]) for row in rows),
    }
    out["performance"] = {
        field: distribution([float(row[field]) for row in rows])
        for field in (
            "T_COST",
            "first_stage_cost",
            "worst_exercise_cost",
            "worst_shortage_penalty",
            "budget_usage",
        )
    }
    out["numerical_recovery"] = {
        "runs_with_recovery": sum(int(row["scaled_retry_count"]) > 0 for row in rows),
        "scaled_retry_evaluations": sum(int(row["scaled_retry_count"]) for row in rows),
        "witness_gated_retry_evaluations": sum(
            int(row["witness_gated_retry_count"]) for row in rows
        ),
    }
    return out


def matrix(summaries: Mapping[str, Mapping[str, Any]], getter) -> dict[str, Any]:
    return {
        str(retention): {
            str(multiplier): getter(summaries[case_id(retention, multiplier)])
            for multiplier in F_ECONOMICS_LEVELS
        }
        for retention in RETENTION_LEVELS
    }


def audit(
    report: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    summaries: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    expected_ids = [f"LA-{index:04d}" for index in report["S200_ids"]]
    if len(rows) != 1800:
        errors.append("scientific_results does not contain 1,800 rows")
    if set(summaries) != set(CASES) or len(summaries) != 9:
        errors.append("summary does not contain the exact 9-cell grid")
    by_case = {case: [row for row in rows if row["case_id"] == case] for case in CASES}
    for case, cell in by_case.items():
        if len(cell) != 200:
            errors.append(f"{case}: N != 200")
            continue
        if [row["simulation_id"] for row in cell] != expected_ids:
            errors.append(f"{case}: S200 order or membership mismatch")
        if len({row["simulation_id"] for row in cell}) != 200:
            errors.append(f"{case}: duplicate S200 row")
        for row in cell:
            if row.get("certificate_status") != "PASS" or row.get("status") != "certified":
                errors.append(f"{case}/{row['simulation_id']}: not certified")
                continue
            if row.get("algorithm_identity") != FINAL_A1_IDENTITY or row.get(
                "implementation_revision"
            ) != FINAL_A1_IMPLEMENTATION_REVISION:
                errors.append(f"{case}/{row['simulation_id']}: algorithm identity drift")
            q_active = [float(row[f"Q_{label}"]) > POLICY_TOLERANCE for label in OUTPUT_ITEMS.values()]
            f_active = [float(row[f"F_{label}"]) > POLICY_TOLERANCE for label in OUTPUT_ITEMS.values()]
            mixed = any(q_active) and any(f_active)
            same = any(q and f for q, f in zip(q_active, f_active))
            cross = mixed and not same
            if _truth(row["mixed_aggregate_QF"]) != mixed:
                errors.append(f"{case}/{row['simulation_id']}: mixed Q-F identity mismatch")
            if _truth(row["same_item_QF_coexistence"]) != same:
                errors.append(f"{case}/{row['simulation_id']}: same-item identity mismatch")
            if _truth(row["cross_item_specialization"]) != cross:
                errors.append(f"{case}/{row['simulation_id']}: cross-item identity mismatch")
            labels = [str(row[f"R_{label}"]) for label in OUTPUT_ITEMS.values()]
            if any(value not in {"NONE", "R0", "R1", "R2"} for value in labels):
                errors.append(f"{case}/{row['simulation_id']}: invalid R-level label")
            if _truth(row["paid_R_any"]) != any(value in {"R1", "R2"} for value in labels):
                errors.append(f"{case}/{row['simulation_id']}: paid-R identity mismatch")
            if int(row["R1_item_count"]) != labels.count("R1") or int(row["R2_item_count"]) != labels.count("R2"):
                errors.append(f"{case}/{row['simulation_id']}: R-level count mismatch")
        summary = summaries[case]
        if sum(int(value) for value in summary["policy_counts"].values()) != 200:
            errors.append(f"{case}: policy-family counts do not sum to N")
        if int(summary["same_item_QF_count"]) + int(summary["cross_item_QF_count"]) != int(summary["mixed_QF_count"]):
            errors.append(f"{case}: mixed Q-F decomposition mismatch")
        for count_field, rate_field in (
            ("mixed_QF_count", "mixed_QF_rate"),
            ("same_item_QF_count", "same_item_QF_rate"),
            ("cross_item_QF_count", "cross_item_QF_rate"),
        ):
            count = int(summary[count_field])
            if not 0 <= count <= 200 or not math.isclose(
                float(summary[rate_field]), count / 200 * 100.0, abs_tol=1e-12
            ):
                errors.append(f"{case}: {rate_field} is not count/N")
        for commodity, values in summary["commodities"].items():
            for stem in ("Q_activation", "F_activation"):
                count = int(values[f"{stem}_count"])
                if not 0 <= count <= 200 or not math.isclose(
                    float(values[f"{stem}_rate"]), count / 200 * 100.0, abs_tol=1e-12
                ):
                    errors.append(f"{case}/{commodity}: {stem} rate mismatch")
        reliability = summary["reliability"]
        for stem in ("paid_R", "R1_case", "R2_case"):
            count = int(reliability[f"{stem}_count"])
            if not 0 <= count <= 200 or not math.isclose(
                float(reliability[f"{stem}_rate"]), count / 200 * 100.0, abs_tol=1e-12
            ):
                errors.append(f"{case}: {stem} rate mismatch")
    return {
        "status": "PASS" if not errors else "FAIL",
        "checks": {
            "cell_count": len(summaries),
            "per_cell_N": 200,
            "total_N": len(rows),
            "S200_identity": report["S200_sha256"],
            "rates_derived_from_counts": not any("rate" in error for error in errors),
            "policy_identities_checked": True,
            "reliability_identities_checked": True,
            "commodity_traceability_checked": True,
        },
        "errors": errors,
    }
