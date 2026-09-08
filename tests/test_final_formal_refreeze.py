import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/final_formal_scientific_design_v1.json").read_text(encoding="utf-8"))
AUDIT = json.loads((ROOT / "docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json").read_text(encoding="utf-8"))


def test_final_authority_has_zero_runs_and_rawls24_identity():
    assert CONFIG["status"] == "FROZEN_DESIGN_EXECUTION_NOT_AUTHORIZED"
    assert CONFIG["scientific_optimization_runs"] == 0
    assert CONFIG["common"]["scenario_order"] == [f"h{index:02d}" for index in range(1, 25)]
    assert CONFIG["common"]["scenario_type"] == "single_hurricane"
    assert CONFIG["common"]["B_ref_E1"] == 19137905.85543848
    assert CONFIG["common"]["beta"] == 4.0
    assert CONFIG["common"]["lambda"] == [1.0, 1.0, 1.0]
    assert CONFIG["common"]["data_sources"]["canonical_data_sha256"] == "51d2b286997556a338acf5dd28df4409d67e46bec52a02f737af4ab0ac0c5afb"


def test_final_a1_is_no_memory_and_preserves_exactness_rules():
    algorithm = CONFIG["algorithm"]
    assert algorithm["identity"] == "A1_FINAL_NO_MEMORY_V1"
    assert algorithm["components"] == ["Candidate Search", "Full Exact Certification", "numerically robust exact oracle"]
    assert algorithm["memory_enabled"] is False
    assert algorithm["memory_metrics_formal"] is False
    assert algorithm["validation_tolerance"] == {"rule": "abs_violation <= abs_tol + rel_tol * constraint_family_scale", "absolute": 1e-7, "relative": 1e-12}
    assert algorithm["convergence_tolerance"] == {"absolute": 1e-7, "relative": 1e-9}


def test_e1_frozen_table_and_parameter_space():
    e1 = CONFIG["E1"]
    assert e1["sample_size"] == 1000 and e1["seed"] == 20260903
    assert e1["sample_table_sha256"] == "ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0"
    assert e1["sample_source"]["git_commit"] == AUDIT["pr_head"]
    assert e1["constraints"]["rho_F_vs_rho_Q"] == "NO_CONSTRAINT"
    assert e1["constraints"]["phi_plus_psi"] == "NO_CONSTANT_SUM_CONSTRAINT"
    assert e1["policy_tolerance"] == 1e-7
    assert e1["interpretation"] == "PARAMETER_SPACE_SHARE_NOT_REAL_WORLD_PROBABILITY"
    assert len(e1["bounds"]) == 16


def test_e2_e3_e4_e5_matrix_and_open_decisions():
    assert CONFIG["E2"]["planned_new_optimizations"] == 11000
    assert CONFIG["E3"]["representative_subset"]["size"] == 200
    assert CONFIG["E3"]["B"]["status"] == "OPEN_DECISION_E3B_RELIABILITY_SELECTION"
    assert CONFIG["E4"]["A"]["training_optimizations"] == 4800
    assert CONFIG["E4"]["B"]["status"] == "OPEN_DECISION_E4B_GENERATOR"
    assert CONFIG["E5"]["algorithms"] == ["A0", "A1_FINAL_NO_MEMORY_V1"]
    assert CONFIG["E5"]["timing_repetitions"] == 3
    assert CONFIG["E5"]["B"]["scenario_sizes"] == [50, 100, 200, 500]
    assert CONFIG["E5"]["C"]["item_sizes"] == [3, 6, 9]
    assert set(CONFIG["open_decisions"]) >= {"OPEN_DECISION_E3B_RELIABILITY_SELECTION", "OPEN_DECISION_E4B_GENERATOR"}


def test_pr27_static_audit_is_complete_and_scoped():
    assert AUDIT["pr_number"] == 27
    assert AUDIT["pr_head"] == "675759cf955788d0200e8c1f24e7e1aff13af44b"
    assert AUDIT["counts"] == {"PASS": 25, "FAIL": 0, "UNKNOWN": 0}
    assert AUDIT["FINAL_E1_REUSE_CANDIDATE"] == "YES"
    assert AUDIT["reuse_scope"] == "E1_SCIENTIFIC_OUTPUTS_ONLY_PENDING_INDEPENDENT_APPROVAL"
    assert AUDIT["scientific_optimization_runs"] == 0
    assert AUDIT["sampler_reconstruction"]["matches_committed_sample_bytes"] is True
    assert AUDIT["pr_artifact_hash_entries_verified"] == 53
    assert AUDIT["pr_artifact_hash_failures"] == []


def test_pr27_memory_was_enabled_but_inert_for_scientific_path():
    memory = AUDIT["memory_effect_audit"]
    assert memory["solve_count"] == memory["memory_phase_enabled_count"] == 1000
    assert memory["memory_exact_evaluations"] == 2000
    assert memory["memory_hits"] == 0
    assert memory["candidate_plan_changes_vs_memory_disabled"] == 0
    assert memory["full_exact_after_memory_miss"] == 1000
    assert {"E5 runtime", "E5 scenario-evaluation counts", "Memory metrics"} <= set(AUDIT["excluded_reuse"])


def test_historical_documents_are_explicitly_superseded_without_changing_frozen_files():
    registry = (ROOT / "docs/FINAL_FORMAL_SUPERSEDED_REGISTRY_v1.md").read_text(encoding="utf-8")
    assert "SUPERSEDED / HISTORICAL_ONLY" in registry
    for token in ("RESEARCH_DESIGN_v1.md", "R7_E1_PROTOCOL_v1.md", "N5_A1_PROTOCOL.md", "12/24-item", "A1_full", "51-scenario"):
        assert token in registry


def test_audit_tool_is_static_and_contains_no_scientific_solver_entrypoint():
    source = (ROOT / "scripts/audit_pr27_final_e1_identity.py").read_text(encoding="utf-8")
    assert "solve_qfr" not in source
    assert "pyomo" not in source
    assert "gurobipy" not in source
    assert "SCIENTIFIC OPTIMIZATION RUNS" in (ROOT / "docs/FINAL_FORMAL_SCIENTIFIC_DESIGN_v1.md").read_text(encoding="utf-8")


def test_final_design_hash_manifest():
    manifest = ROOT / "docs/FINAL_FORMAL_DESIGN_HASHES_v1.sha256"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
