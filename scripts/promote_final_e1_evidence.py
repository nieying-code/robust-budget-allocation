"""Promote audited PR #27 Layer B science into canonical Final E1 evidence.

This script is solver-free.  It reads immutable Git blobs, validates the frozen
identity and the prior 25/25 audit, recomputes policy/activation summaries, and
writes only whitelisted scientific evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence


SOURCE_PR = 27
SOURCE_HEAD = "675759cf955788d0200e8c1f24e7e1aff13af44b"
SOURCE_ROOT = "simulation_results/qfr_mechanism_layer_b_rawls24_n1000"
SOURCE_SAMPLE = f"{SOURCE_ROOT}/samples.csv"
SOURCE_RESULTS = f"{SOURCE_ROOT}/scientific_results.csv"
SOURCE_HASHES = f"{SOURCE_ROOT}/HASHES.sha256"
SOURCE_MANIFEST = f"{SOURCE_ROOT}/simulation_manifest.json"

BASE_MAIN = "5f1d20a1c1cff18eceeb1f840866495e98df9812"
PROMOTION_BRANCH = "r9/e1-evidence-promotion"
FINAL_ALGORITHM = "A1_FINAL_NO_MEMORY_V1"
HISTORICAL_ALGORITHM = "A1_full"
EXPECTED_SAMPLE_SHA256 = "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
EXPECTED_SOURCE_RESULTS_SHA256 = "96a9d130d47d7c9a875e7340d936542275da9e6afc9248b008fe02419a93c9eb"
EXPECTED_AUDIT_SHA256 = "b7756235dba5b418eb2cafb6a3df0401e6739889552a6603faad66a31ce00411"
EXPECTED_FINAL_CONFIG_SHA256 = "106c84d1abe38cb5a96b3e7dd8de417928c15bd993b4254534aefa26c7801621"
EXPECTED_FINAL_A1_SOURCE_SHA256 = "3c89ac2db4e1530130e4e32928390b0cc0c5792976a1959342ceee8c4794c249"
EXPECTED_FINAL_A1_EVIDENCE_SHA256 = "7b72c1cf4c17a24c5cdf2e2e92431abbb75c1aafef584f2118a8cb91e9849bba"
CURRENT_FINAL_A1_SOURCE_SHA256 = "bd8987e7ef117218db2c828547303aa324d020a8e362b26dba7daf3f1b416ea5"
CURRENT_FINAL_A1_EVIDENCE_SHA256 = "351699e3da0292bd821ecfb4df74c934b4b8c4b8639c83c1c3ade3c7f653a7b8"

FINAL_CONFIG = "configs/final_formal_scientific_design_v1.json"
IDENTITY_AUDIT = "docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json"
FINAL_A1_SOURCE = "src/robust_budget_allocation/algorithms/qfr_final_a1.py"
FINAL_A1_EVIDENCE = "docs/evidence/FINAL_A1_ENGINEERING_PROMOTION_v1.json"
OUTPUT_ROOT = Path("formal_results/e1_final")
POLICY_TOLERANCE = 1e-7
ITEMS = ("Water", "Vaccine", "Crackers")
SOURCE_ITEM = {
    "Water": "Water",
    "Vaccine": "Seasonal Influenza Vaccine",
    "Crackers": "Crackers",
}
LEVELS = ("NONE", "R0", "R1", "R2")
POLICIES = ("P1", "P2", "P3a", "P3b", "P4", "P5")
EXPECTED_POLICY_COUNTS = {"P1": 208, "P2": 26, "P3a": 4, "P3b": 3, "P4": 759, "P5": 0}
EXPECTED_COMMODITY = {
    "Water": {"Q_active": 241, "F_active": 356, "NONE": 644, "R0": 343, "R1": 5, "R2": 8},
    "Vaccine": {"Q_active": 208, "F_active": 225, "NONE": 775, "R0": 158, "R1": 49, "R2": 18},
    "Crackers": {"Q_active": 0, "F_active": 579, "NONE": 421, "R0": 522, "R1": 32, "R2": 25},
}
EXPECTED_RELIABILITY = {"NONE": 1840, "R0": 1023, "R1": 86, "R2": 51}
EXPECTED_MIXED = 33
EXPECTED_SAME_ITEM = 0
EXPECTED_WORST = {"h09": 1000}
EXPECTED_CROSS_SPECIALIZATION = {
    "Q[Water]|F[Crackers]": 24,
    "Q[Water]|F[Vaccine]": 9,
}

SAMPLE_COLUMNS = (
    "simulation_id", "sample_index", "simulation_seed",
    "rho_Q1", "rho_Q2", "rho_Q3", "rho_Q4", "rho_Q5",
    "rho_F1", "rho_F2", "rho_F3", "rho_F4", "rho_F5",
    "eta_1", "eta_2", "phi", "psi", "c_R1_ratio", "c_R2_ratio",
    "input_sha256",
)

RESULT_COLUMNS = (
    "simulation_id", "sample_index", "input_sha256", "model_kind",
    "algorithm_identity", "certificate_status", "data_sha256", "scenario_sha256",
    "first_stage_sha256", "policy_label",
    "Q_Water", "Q_Vaccine", "Q_Crackers",
    "F_Water", "F_Vaccine", "F_Crackers",
    "R_Water", "R_Vaccine", "R_Crackers",
    "z_R0_Water", "z_R1_Water", "z_R2_Water",
    "z_R0_Vaccine", "z_R1_Vaccine", "z_R2_Vaccine",
    "z_R0_Crackers", "z_R1_Crackers", "z_R2_Crackers",
    "Q_active_Water", "Q_active_Vaccine", "Q_active_Crackers",
    "F_active_Water", "F_active_Vaccine", "F_active_Crackers",
    "same_item_QF_Water", "same_item_QF_Vaccine", "same_item_QF_Crackers",
    "same_item_QF_coexistence", "cross_item_specialization", "portfolio_pattern",
    "T_COST", "certified_objective", "C_Q", "C_F", "C_R", "first_stage_cost",
    "worst_scenario", "worst_category", "worst_hurricane", "exact_worst_case_loss",
    "worst_exercise_cost", "worst_shortage_penalty", "worst_total_shortage",
    "worst_total_F_exercise", "budget_usage",
    "worst_exercise_Water", "worst_exercise_Vaccine", "worst_exercise_Crackers",
    "worst_shortage_Water", "worst_shortage_Vaccine", "worst_shortage_Crackers",
    "promoted_row_sha256",
)

FORBIDDEN_RESULT_FIELDS = frozenset(
    {
        "runtime_seconds", "timing_metrics", "scenario_evaluations",
        "evaluation_count", "memory_hits", "memory_inspections",
        "memory_exact_evaluations", "memory_cache_statistics",
        "historical_algorithm_label", "algorithm_kind", "a1_result_sha256",
        "oracle_sha256", "execution_git_commit", "execution_git_tree",
    }
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _git_blob(repo: Path, revision: str, relative: str) -> bytes:
    outcome = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if outcome.returncode:
        raise RuntimeError(
            f"required immutable source blob unavailable: {revision}:{relative}: "
            f"{outcome.stderr.decode(errors='replace').strip()}"
        )
    return outcome.stdout


def _read_csv(data: bytes) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")
    rows = [dict(row) for row in reader]
    return tuple(reader.fieldnames), rows


def _csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        if set(row) != set(columns):
            raise ValueError("promoted CSV row does not exactly match its canonical schema")
        writer.writerow({column: row[column] for column in columns})
    return stream.getvalue().encode("utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_close(left: float, right: float, label: str) -> None:
    threshold = 1e-7 + 1e-9 * max(1.0, abs(left), abs(right))
    if abs(left - right) > threshold:
        raise ValueError(f"{label} mismatch: {left!r} != {right!r}")


def _validate_local_identities(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config_path = repo / FINAL_CONFIG
    audit_path = repo / IDENTITY_AUDIT
    a1_path = repo / FINAL_A1_SOURCE
    a1_evidence_path = repo / FINAL_A1_EVIDENCE
    frozen_expected = {
        config_path: EXPECTED_FINAL_CONFIG_SHA256,
        audit_path: EXPECTED_AUDIT_SHA256,
    }
    for path, digest in frozen_expected.items():
        if _file_sha256(path) != digest:
            raise ValueError(f"frozen identity hash mismatch: {path.relative_to(repo)}")
    # E1's historical re-registration remains byte-stable, while the live Final
    # A1 implementation may advance through an independently audited engineering
    # revision that does not alter E1 scientific evidence.
    if _file_sha256(a1_path) not in {
        EXPECTED_FINAL_A1_SOURCE_SHA256,
        CURRENT_FINAL_A1_SOURCE_SHA256,
    }:
        raise ValueError(f"Final A1 implementation hash mismatch: {a1_path.relative_to(repo)}")
    if _file_sha256(a1_evidence_path) not in {
        EXPECTED_FINAL_A1_EVIDENCE_SHA256,
        CURRENT_FINAL_A1_EVIDENCE_SHA256,
    }:
        raise ValueError(
            f"Final A1 engineering evidence hash mismatch: {a1_evidence_path.relative_to(repo)}"
        )

    config = _load_json(config_path)
    audit = _load_json(audit_path)
    if config["status"] != "FROZEN_DESIGN_EXECUTION_NOT_AUTHORIZED":
        raise ValueError("Final design status mismatch")
    if config["common"]["dataset"] != "rawls_24_real_single_hurricane_data_recalibration_v1":
        raise ValueError("Final E1 dataset mismatch")
    if config["common"]["scenario_order"] != [f"h{index:02d}" for index in range(1, 25)]:
        raise ValueError("Final E1 scenario order mismatch")
    if config["common"]["commodities"] != ["Water", "Seasonal Influenza Vaccine", "Crackers"]:
        raise ValueError("Final E1 commodity identity mismatch")
    expected_common = {
        "model": "M2", "beta": 4.0, "lambda": [1.0, 1.0, 1.0],
        "gamma_D": 1.0, "B_ref_E1": 19137905.85543848,
    }
    for field, value in expected_common.items():
        if config["common"][field] != value:
            raise ValueError(f"Final E1 common identity mismatch: {field}")
    if config["algorithm"]["identity"] != FINAL_ALGORITHM or config["algorithm"]["memory_enabled"] is not False:
        raise ValueError("Final A1 identity mismatch")
    e1 = config["E1"]
    if (
        e1["sample_size"] != 1000
        or e1["sampling"] != "DETERMINISTIC_CONSTRAINED_LATIN_HYPERCUBE_V1"
        or e1["seed"] != 20260903
        or e1["sample_table_sha256"] != EXPECTED_SAMPLE_SHA256
        or e1["policy_tolerance"] != POLICY_TOLERANCE
    ):
        raise ValueError("Final E1 sampling identity mismatch")

    if (
        audit["pr_number"] != SOURCE_PR
        or audit["pr_head"] != SOURCE_HEAD
        or audit["FINAL_E1_REUSE_CANDIDATE"] != "YES"
        or audit["counts"] != {"FAIL": 0, "PASS": 25, "UNKNOWN": 0}
        or audit["pr_artifact_hash_entries_verified"] != 53
        or audit["pr_artifact_hash_failures"] != []
        or audit["sample_table_sha256"] != EXPECTED_SAMPLE_SHA256
    ):
        raise ValueError("PR #28 reuse audit is not the frozen 25/25 PASS identity")
    memory = audit["memory_effect_audit"]
    if not (
        memory["solve_count"] == 1000
        and memory["memory_hits"] == 0
        and memory["candidate_plan_changes_vs_memory_disabled"] == 0
        and memory["full_exact_after_memory_miss"] == 1000
    ):
        raise ValueError("historical algorithm inertness audit failed")
    return config, audit


def _source_inventory(repo: Path) -> tuple[dict[str, str], dict[str, bytes]]:
    hashes_blob = _git_blob(repo, SOURCE_HEAD, SOURCE_HASHES)
    inventory: dict[str, str] = {}
    for line in hashes_blob.decode("utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in inventory or len(digest) != 64:
            raise ValueError("invalid PR #27 source hash inventory")
        inventory[relative] = digest
    if len(inventory) != 53:
        raise ValueError("PR #27 source hash inventory must contain exactly 53 entries")
    blobs: dict[str, bytes] = {}
    for relative, digest in inventory.items():
        blob = _git_blob(repo, SOURCE_HEAD, f"{SOURCE_ROOT}/{relative}")
        if _sha256(blob) != digest:
            raise ValueError(f"PR #27 source artifact hash mismatch: {relative}")
        blobs[relative] = blob
    if inventory.get("samples.csv") != EXPECTED_SAMPLE_SHA256:
        raise ValueError("source sample SHA mismatch")
    if inventory.get("scientific_results.csv") != EXPECTED_SOURCE_RESULTS_SHA256:
        raise ValueError("source scientific result SHA mismatch")
    return inventory, blobs


def _validate_samples(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> None:
    if tuple(header) != SAMPLE_COLUMNS or len(rows) != 1000:
        raise ValueError("source sample schema/count mismatch")
    ids = [row["simulation_id"] for row in rows]
    expected_ids = [f"LA-{index:04d}" for index in range(1, 1001)]
    if ids != expected_ids or len(ids) != len(set(ids)):
        raise ValueError("source sample IDs are missing, duplicated, or reordered")
    for index, row in enumerate(rows, 1):
        if int(row["sample_index"]) != index or int(row["simulation_seed"]) != 20260903:
            raise ValueError("source sample index/seed mismatch")
        if len(row["input_sha256"]) != 64:
            raise ValueError("source input identity is malformed")
        for column in SAMPLE_COLUMNS[3:-1]:
            if not math.isfinite(float(row[column])):
                raise ValueError(f"nonfinite source sample parameter: {column}")


def _classify(q: Mapping[str, float], f: Mapping[str, float], r: Mapping[str, str]) -> str:
    q_active = any(value > POLICY_TOLERANCE for value in q.values())
    active_items = [item for item, value in f.items() if value > POLICY_TOLERANCE]
    if q_active and not active_items:
        return "P1"
    if active_items and not q_active:
        return "P4"
    if q_active and active_items:
        active_levels = {r[item] for item in active_items}
        if "R2" in active_levels:
            return "P3b"
        if "R1" in active_levels:
            return "P3a"
        if active_levels == {"R0"}:
            return "P2"
    return "P5"


def _promote_rows(
    samples: Sequence[Mapping[str, str]],
    source_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    if len(source_rows) != 1000:
        raise ValueError("source scientific row count is not 1000")
    promoted: list[dict[str, Any]] = []
    for index, (sample, source) in enumerate(zip(samples, source_rows, strict=True), 1):
        if source["simulation_id"] != sample["simulation_id"] or int(source["sample_index"]) != index:
            raise ValueError("scientific/sample row traceability mismatch")
        if source["input_sha256"] != sample["input_sha256"]:
            raise ValueError("scientific/sample input hash mismatch")
        for column in SAMPLE_COLUMNS[3:-1]:
            if source[column] != sample[column]:
                raise ValueError(f"scientific/frozen parameter mismatch: {source['simulation_id']} {column}")
        if (
            source["model_kind"] != "M2"
            or source["algorithm_kind"] != HISTORICAL_ALGORITHM
            or source["status"] != "SUCCESS"
            or source["convergence_status"] != "certified"
            or source["certificate_status"] != "PASS"
            or source["sample_table_sha256"] != EXPECTED_SAMPLE_SHA256
        ):
            raise ValueError(f"uncertified or wrong-identity source row: {source['simulation_id']}")
        _require_close(float(source["budget"]), 19137905.85543848, "budget")
        _require_close(float(source["shortage_beta"]), 4.0, "beta")
        _require_close(float(source["demand_scale_gamma_D"]), 1.0, "gamma_D")

        q = {item: float(source[f"Q_{SOURCE_ITEM[item]}"]) for item in ITEMS}
        f = {item: float(source[f"F_{SOURCE_ITEM[item]}"]) for item in ITEMS}
        r = {item: source[f"R_{SOURCE_ITEM[item]}"] for item in ITEMS}
        for item in ITEMS:
            if r[item] not in LEVELS:
                raise ValueError(f"invalid reliability level: {source['simulation_id']} {item}")
            if f[item] <= POLICY_TOLERANCE and r[item] != "NONE":
                raise ValueError(f"inactive F has a reliability level: {source['simulation_id']} {item}")
            if f[item] > POLICY_TOLERANCE and r[item] == "NONE":
                raise ValueError(f"active F lacks a reliability level: {source['simulation_id']} {item}")
        label = _classify(q, f, r)
        if label != source["policy_label"]:
            raise ValueError(f"recomputed policy label mismatch: {source['simulation_id']}")

        q_items = [item for item in ITEMS if q[item] > POLICY_TOLERANCE]
        f_items = [item for item in ITEMS if f[item] > POLICY_TOLERANCE]
        same = {item: q[item] > POLICY_TOLERANCE and f[item] > POLICY_TOLERANCE for item in ITEMS}
        cross_specialization = bool(q_items and f_items and not any(same.values()))
        portfolio = f"Q[{'+'.join(q_items) or 'NONE'}]|F[{'+'.join(f_items) or 'NONE'}]"
        exact_worst_loss = float(source["worst_exercise_cost"]) + float(source["worst_shortage_penalty"])
        objective = float(source["objective_T_COST"])
        _require_close(
            objective,
            float(source["first_stage_cost"]) + exact_worst_loss,
            f"certified objective {source['simulation_id']}",
        )

        row: dict[str, Any] = {
            "simulation_id": source["simulation_id"],
            "sample_index": index,
            "input_sha256": source["input_sha256"],
            "model_kind": "M2",
            "algorithm_identity": FINAL_ALGORITHM,
            "certificate_status": "PASS",
            "data_sha256": source["data_sha256"],
            "scenario_sha256": source["scenario_sha256"],
            "first_stage_sha256": source["first_stage_sha256"],
            "policy_label": label,
            "same_item_QF_coexistence": any(same.values()),
            "cross_item_specialization": cross_specialization,
            "portfolio_pattern": portfolio,
            "T_COST": source["objective_T_COST"],
            "certified_objective": source["objective_T_COST"],
            "C_Q": source["C_Q"], "C_F": source["C_F"], "C_R": source["C_R"],
            "first_stage_cost": source["first_stage_cost"],
            "worst_scenario": source["worst_scenario"],
            "worst_category": source["worst_category"],
            "worst_hurricane": source["worst_hurricane"],
            "exact_worst_case_loss": repr(exact_worst_loss),
            "worst_exercise_cost": source["worst_exercise_cost"],
            "worst_shortage_penalty": source["worst_shortage_penalty"],
            "worst_total_shortage": source["worst_total_shortage"],
            "worst_total_F_exercise": source["worst_total_F_exercise"],
            "budget_usage": source["budget_usage"],
        }
        for item in ITEMS:
            source_item = SOURCE_ITEM[item]
            row[f"Q_{item}"] = source[f"Q_{source_item}"]
            row[f"F_{item}"] = source[f"F_{source_item}"]
            row[f"R_{item}"] = r[item]
            for level in ("R0", "R1", "R2"):
                row[f"z_{level}_{item}"] = int(r[item] == level)
            row[f"Q_active_{item}"] = q[item] > POLICY_TOLERANCE
            row[f"F_active_{item}"] = f[item] > POLICY_TOLERANCE
            row[f"same_item_QF_{item}"] = same[item]
            row[f"worst_exercise_{item}"] = source[f"worst_exercise_{source_item}"]
            row[f"worst_shortage_{item}"] = source[f"worst_shortage_{source_item}"]
        row["promoted_row_sha256"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if set(row) != set(RESULT_COLUMNS):
            raise ValueError("promoted scientific row schema mismatch")
        promoted.append(row)
    return promoted


def _summaries(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    policy_counts = {label: sum(row["policy_label"] == label for row in rows) for label in POLICIES}
    policy = {
        "schema_version": 1,
        "row_count": len(rows),
        "policy_tolerance": POLICY_TOLERANCE,
        "counts": policy_counts,
        "shares": {label: policy_counts[label] / len(rows) for label in POLICIES},
        "interpretation": "PARAMETER_SPACE_SHARE_NOT_REAL_WORLD_PROBABILITY",
    }
    commodity: dict[str, Any] = {}
    aggregate = {level: 0 for level in LEVELS}
    for item in ITEMS:
        reliability = {level: sum(row[f"R_{item}"] == level for row in rows) for level in LEVELS}
        for level, count in reliability.items():
            aggregate[level] += count
        commodity[item] = {
            "Q_active": sum(bool(row[f"Q_active_{item}"]) for row in rows),
            "F_active": sum(bool(row[f"F_active_{item}"]) for row in rows),
            "reliability": reliability,
            "same_item_QF_coexistence": sum(bool(row[f"same_item_QF_{item}"]) for row in rows),
        }
    mixed_rows = [row for row in rows if row["policy_label"] in {"P2", "P3a", "P3b"}]
    cross_counts: dict[str, int] = {}
    portfolio_counts: dict[str, int] = {}
    for row in rows:
        pattern = str(row["portfolio_pattern"])
        portfolio_counts[pattern] = portfolio_counts.get(pattern, 0) + 1
    for row in mixed_rows:
        pattern = str(row["portfolio_pattern"])
        cross_counts[pattern] = cross_counts.get(pattern, 0) + 1
    commodity_summary = {
        "schema_version": 1,
        "row_count": len(rows),
        "policy_tolerance": POLICY_TOLERANCE,
        "commodities": commodity,
        "aggregate_reliability": aggregate,
        "mixed_aggregate_Q_plus_F": len(mixed_rows),
        "same_item_QF_coexistence": sum(bool(row["same_item_QF_coexistence"]) for row in rows),
        "mixed_cross_item_specialization": dict(sorted(cross_counts.items())),
        "all_portfolio_patterns": dict(sorted(portfolio_counts.items())),
    }
    worst_counts: dict[str, int] = {}
    hurricane_counts: dict[str, int] = {}
    for row in rows:
        scenario = str(row["worst_scenario"])
        hurricane = str(row["worst_hurricane"])
        worst_counts[scenario] = worst_counts.get(scenario, 0) + 1
        hurricane_counts[hurricane] = hurricane_counts.get(hurricane, 0) + 1
    worst = {
        "schema_version": 1,
        "row_count": len(rows),
        "scenario_counts": dict(sorted(worst_counts.items())),
        "hurricane_counts": dict(sorted(hurricane_counts.items())),
    }
    return policy, commodity_summary, worst


def _validate_targets(policy: Mapping[str, Any], commodity: Mapping[str, Any], worst: Mapping[str, Any]) -> None:
    if policy["counts"] != EXPECTED_POLICY_COUNTS:
        raise ValueError("recomputed policy-count target mismatch")
    for item, expected in EXPECTED_COMMODITY.items():
        actual = commodity["commodities"][item]
        flattened = {
            "Q_active": actual["Q_active"], "F_active": actual["F_active"],
            **actual["reliability"],
        }
        if flattened != expected:
            raise ValueError(f"recomputed commodity target mismatch: {item}")
    if commodity["aggregate_reliability"] != EXPECTED_RELIABILITY:
        raise ValueError("aggregate reliability target mismatch")
    if commodity["mixed_aggregate_Q_plus_F"] != EXPECTED_MIXED:
        raise ValueError("mixed aggregate policy target mismatch")
    if commodity["same_item_QF_coexistence"] != EXPECTED_SAME_ITEM:
        raise ValueError("same-item Q/F target mismatch")
    if commodity["mixed_cross_item_specialization"] != EXPECTED_CROSS_SPECIALIZATION:
        raise ValueError("mixed cross-item specialization target mismatch")
    if worst["scenario_counts"] != EXPECTED_WORST:
        raise ValueError("worst-scenario target mismatch")


def _schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "FINAL_E1_SCIENTIFIC_EVIDENCE_ONLY",
        "sample_columns": list(SAMPLE_COLUMNS),
        "scientific_result_columns": list(RESULT_COLUMNS),
        "forbidden_result_fields": sorted(FORBIDDEN_RESULT_FIELDS),
        "algorithm_identity": FINAL_ALGORITHM,
        "policy_tolerance": POLICY_TOLERANCE,
        "supports": ["E2_BASELINE_REUSE", "E3_F_ACTIVE_FILTERING", "E3_REPRESENTATIVE_ANALYSIS", "E4_FULL24_BASELINE_COMPARISON"],
        "does_not_support": ["E5_ALGORITHM_PERFORMANCE", "TIMING_OR_SPEEDUP", "MEMORY_CONTRIBUTION"],
    }


def promote(repo: Path, output_root: Path) -> dict[str, Any]:
    repo = repo.resolve()
    output_root = (repo / output_root).resolve() if not output_root.is_absolute() else output_root.resolve()
    config, audit = _validate_local_identities(repo)
    inventory, blobs = _source_inventory(repo)
    sample_header, samples = _read_csv(blobs["samples.csv"])
    source_header, source_rows = _read_csv(blobs["scientific_results.csv"])
    _validate_samples(samples, sample_header)
    if _sha256(blobs["samples.csv"]) != EXPECTED_SAMPLE_SHA256:
        raise ValueError("source sample bytes do not match frozen Final E1 sample")
    if len(set(source_header)) != len(source_header):
        raise ValueError("source scientific schema contains duplicate fields")
    promoted = _promote_rows(samples, source_rows)
    if any(FORBIDDEN_RESULT_FIELDS.intersection(row) for row in promoted):
        raise ValueError("forbidden historical field entered promoted evidence")
    policy, commodity, worst = _summaries(promoted)
    _validate_targets(policy, commodity, worst)

    files: dict[str, bytes] = {
        "e1_samples.csv": blobs["samples.csv"],
        "e1_scientific_results.csv": _csv_bytes(RESULT_COLUMNS, promoted),
        "e1_policy_summary.json": _canonical_json_bytes(policy),
        "e1_commodity_summary.json": _canonical_json_bytes(commodity),
        "e1_worst_scenario_summary.json": _canonical_json_bytes(worst),
        "e1_output_schema.json": _canonical_json_bytes(_schema()),
    }
    promoted_hashes = {name: _sha256(data) for name, data in files.items()}
    provenance = {
        "schema_version": 1,
        "scope": "FINAL_E1_EVIDENCE_PROMOTION_V1",
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "promotion_method": "READ_ONLY_EXTRACTION_AND_RE_REGISTRATION",
        "no_rerun": True,
        "scientific_optimization_runs": 0,
        "current_main_base_commit": BASE_MAIN,
        "promotion_branch": PROMOTION_BRANCH,
        "final_e1_identity": {
            "dataset": config["common"]["dataset"],
            "scenarios": config["common"]["scenario_order"],
            "commodities": config["common"]["commodities"],
            "model": "M2",
            "algorithm": FINAL_ALGORITHM,
            "budget": 19137905.85543848,
            "beta": 4.0,
            "lambda": [1.0, 1.0, 1.0],
            "gamma_D": 1.0,
            "sample_size": 1000,
            "sampling": "DETERMINISTIC_CONSTRAINED_LATIN_HYPERCUBE_V1",
            "seed": 20260903,
            "sample_sha256": EXPECTED_SAMPLE_SHA256,
        },
        "source": {
            "pull_request": SOURCE_PR,
            "head": SOURCE_HEAD,
            "root": SOURCE_ROOT,
            "directly_extracted": {
                SOURCE_SAMPLE: inventory["samples.csv"],
                SOURCE_RESULTS: inventory["scientific_results.csv"],
                SOURCE_HASHES: _sha256(_git_blob(repo, SOURCE_HEAD, SOURCE_HASHES)),
                SOURCE_MANIFEST: inventory["simulation_manifest.json"],
            },
            "verified_hash_inventory": {
                f"{SOURCE_ROOT}/{relative}": digest for relative, digest in sorted(inventory.items())
            },
            "verified_artifact_count": len(inventory),
        },
        "identity_audit": {
            "path": IDENTITY_AUDIT,
            "sha256": EXPECTED_AUDIT_SHA256,
            "result": audit["FINAL_E1_REUSE_CANDIDATE"],
            "checks": audit["counts"],
            "algorithm_inertness": {
                "memory_hits": 0,
                "candidate_plan_changes": 0,
                "full_exact_after_miss": 1000,
            },
        },
        "final_a1_implementation": {
            "path": FINAL_A1_SOURCE,
            "sha256": EXPECTED_FINAL_A1_SOURCE_SHA256,
            "engineering_evidence_path": FINAL_A1_EVIDENCE,
            "engineering_evidence_sha256": EXPECTED_FINAL_A1_EVIDENCE_SHA256,
            "identity": FINAL_ALGORITHM,
        },
        "algorithm_identity_translation": {
            "historical_execution_identity": "R4_V2_A1_IMPROVED_CCG / A1_full",
            "final_scientific_algorithm_identity": FINAL_ALGORITHM,
            "basis": "PR28_25_OF_25_IDENTITY_AUDIT_MEMORY_INERT_FOR_ALL_1000_OUTCOMES",
            "runtime_or_process_evidence_re_registered": False,
        },
        "promoted_fields": list(RESULT_COLUMNS),
        "excluded_historical_fields": sorted(FORBIDDEN_RESULT_FIELDS | {
            "A1_full_vs_no_memory_ablation", "Layer_A_homogeneous_results",
            "Layer_A_vs_Layer_B_runtime_claims", "E5_computational_claims",
        }),
        "promoted_artifact_sha256": promoted_hashes,
        "row_count": len(promoted),
        "validation_targets": {
            "policy_counts": EXPECTED_POLICY_COUNTS,
            "commodity_activation": EXPECTED_COMMODITY,
            "aggregate_reliability": EXPECTED_RELIABILITY,
            "mixed_aggregate_Q_plus_F": EXPECTED_MIXED,
            "same_item_QF_coexistence": EXPECTED_SAME_ITEM,
            "mixed_cross_item_specialization": EXPECTED_CROSS_SPECIALIZATION,
            "worst_scenario_counts": EXPECTED_WORST,
        },
    }
    files["e1_provenance_manifest.json"] = _canonical_json_bytes(provenance)
    hashes = {name: _sha256(data) for name, data in files.items()}
    files["HASHES.sha256"] = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(hashes.items())
    ).encode("utf-8")

    if output_root.exists():
        existing = {path.name: path.read_bytes() for path in output_root.iterdir() if path.is_file()}
        if existing != files:
            raise FileExistsError("existing Final E1 output differs from deterministic rebuild")
    else:
        output_root.mkdir(parents=True)
        for name, data in files.items():
            (output_root / name).write_bytes(data)
    return {
        "status": "PASS",
        "output_root": str(output_root),
        "row_count": len(promoted),
        "sample_sha256": promoted_hashes["e1_samples.csv"],
        "result_sha256": promoted_hashes["e1_scientific_results.csv"],
        "policy_counts": policy["counts"],
        "scientific_optimization_runs": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(promote(arguments.repo_root, arguments.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
