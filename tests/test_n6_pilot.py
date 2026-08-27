"""N6 engineering/fixture tests; synthetic failures are never pilot successes."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.io.locking import exclusive_file_lock
from robust_budget_allocation.pilot.configuration import (
    ROOT, registration, generate, binding, scenario_payload, execution_order)
from robust_budget_allocation.pilot.execution import supervise, peak_rss, terminate_worker
from robust_budget_allocation.pilot.storage import (
    RUN_FILES, FAILURE_STATES, reserve, normalize_failure, safe_id, safe_relative,
    seal, check_seal, file_manifest, read_run, verify_inventory, inspect_run)
from robust_budget_allocation.pilot.measurement import solve_ablation, verify_ablation


def test_fixed_registration_and_no_extra_combinations():
    reg = registration()
    assert len(reg["configs"]) == 16
    assert reg["seeds"] == [61001, 61002]
    assert {c["budget"] for c in reg["configs"]} == {45, 90, 150}
    assert {c["scenarios"] for c in reg["configs"]} == {12, 24}
    assert len({c["id"] for c in reg["configs"]}) == 16
    assert execution_order(0)[-2:] == ("A0", "A1")
    assert execution_order(1)[-2:] == ("A1", "A0")
    forged = deepcopy(reg["configs"][0])
    forged["budget"] += 1
    with pytest.raises(ValueError, match="unregistered"):
        generate(forged)


@pytest.mark.parametrize("config", registration()["configs"], ids=lambda c: c["id"])
def test_registered_data_validation_and_determinism(config):
    first = generate(config)
    first.validate()
    assert first.to_dict() == generate(config).to_dict()
    assert first.base.shortage_penalty > 0
    assert first.option_fee > 0 and first.option_cap > 0
    assert first.base.resource_id == "resource"
    assert first.base.scenarios == tuple(sorted(first.base.scenarios))
    assert binding(config, first)["scenario_sha256"] == canonical_json_sha256(scenario_payload(first))


def test_common_random_numbers_and_nested_size():
    reg = registration()["configs"]
    low = generate(next(c for c in reg if c["risk"] == "low" and c["seed"] == 61001 and c["budget"] == 90))
    high = generate(next(c for c in reg if c["risk"] == "high" and c["seed"] == 61001 and c["budget"] == 90))
    big = generate(next(c for c in reg if c["seed"] == 61001 and c["scenarios"] == 24))
    assert low.base.demand == high.base.demand
    assert low.emergency_price == high.emergency_price
    for w in high.base.scenarios:
        assert high.base.demand[w] == big.base.demand[w]
        assert high.reliability.fulfillment[w] == big.reliability.fulfillment[w]
        for j in high.base.suppliers:
            assert high.base.base_fulfillment[w][j] <= low.base.base_fulfillment[w][j]


@pytest.mark.parametrize("status", sorted(FAILURE_STATES))
def test_failure_classification_never_success(status):
    assert normalize_failure(status) == status


@pytest.mark.parametrize("status", ["error", "locally_optimal", "unknown", "invalid_solver_status", None])
def test_invalid_status_never_success(status):
    assert normalize_failure(status) != "success/certified"


@pytest.mark.parametrize("path", ["../x", "/abs", "D:/file", "a/../b", "a\\b", "a//b", "./a", ""])
def test_unsafe_manifest_paths(path):
    with pytest.raises(ValueError):
        safe_relative(path)


@pytest.mark.parametrize("run_id", ["../x", "/x", "D:x", "a/b", "a b", ""])
def test_unsafe_run_id(run_id):
    with pytest.raises(ValueError):
        safe_id(run_id)


def test_duplicate_run_id_and_stale_file(tmp_path):
    lock = tmp_path / ".locks/r1.lock"
    atomic_write_text(lock, "stale lock file, no live owner")
    with reserve(tmp_path, "r1") as folder:
        assert folder.is_dir()
        with pytest.raises(TimeoutError):
            with reserve(tmp_path, "r1"):
                pass
    with pytest.raises(FileExistsError):
        with reserve(tmp_path, "r1"):
            pass


def test_real_cross_process_lease_and_crash(tmp_path):
    child = """
import sys, time
from pathlib import Path
from robust_budget_allocation.pilot.storage import reserve
from robust_budget_allocation.io.atomic import atomic_write_json
with reserve(Path(sys.argv[1]), 'run'):
    atomic_write_json(Path(sys.argv[1])/'run/heartbeat.json', {'stage':'algorithm'})
    print('ready', flush=True)
    time.sleep(30)
"""
    process = subprocess.Popen([sys.executable, "-c", child, str(tmp_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        with pytest.raises(TimeoutError):
            with reserve(tmp_path, "run"):
                pass
    finally:
        terminate_worker(process)
    assert inspect_run(tmp_path / "run") == "interrupted"
    # OS lease released, but abandoned ID remains immutable.
    with exclusive_file_lock(tmp_path / ".locks/run.lock", timeout_seconds=0):
        pass
    with pytest.raises(FileExistsError):
        with reserve(tmp_path, "run"):
            pass


def test_retry_lineage_never_overwrites_parent(tmp_path):
    parent = tmp_path / "failed"
    parent.mkdir()
    original = seal(dict(status="time_limit"), "output_sha256")
    atomic_write_json(parent / "record.json", original)
    with reserve(tmp_path, "retry", parent_run_id="failed", retry_reason="explicit test authorization"):
        pass
    assert json.loads((parent / "record.json").read_text()) == original
    with pytest.raises(ValueError):
        with reserve(tmp_path, "new", parent_run_id="failed"):
            pass


def fake_files(folder):
    for name in RUN_FILES:
        atomic_write_text(folder / name, "{}\n")
    return file_manifest(folder)


def test_atomic_manifest_and_missing_output(tmp_path):
    manifest = fake_files(tmp_path)
    bundle = read_run(tmp_path)
    verify_inventory(manifest, bundle["files"])
    (tmp_path / "result.json").unlink()
    assert inspect_run(tmp_path) == "incomplete"
    with pytest.raises(ValueError):
        read_run(tmp_path)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "absolute", "parent", "hash", "bytes", "extra"])
def test_manifest_forgery_rejected(tmp_path, fault):
    manifest = fake_files(tmp_path)
    files = read_run(tmp_path)["files"]
    if fault == "missing":
        manifest["files"].pop()
    elif fault == "duplicate":
        manifest["files"].append(deepcopy(manifest["files"][0]))
    elif fault == "absolute":
        manifest["files"][0]["path"] = "/tmp/x"
    elif fault == "parent":
        manifest["files"][0]["path"] = "../x"
    elif fault == "hash":
        manifest["files"][0]["sha256"] = "0"*64
    elif fault == "bytes":
        manifest["files"][0]["bytes"] += 1
    else:
        files["extra"] = "{}"
    manifest.pop("sha256")
    manifest = seal(manifest)
    with pytest.raises(ValueError):
        verify_inventory(manifest, files)


def test_nonregular_file_rejected(tmp_path):
    fake_files(tmp_path)
    (tmp_path / "result.json").unlink()
    (tmp_path / "result.json").mkdir()
    with pytest.raises(ValueError):
        read_run(tmp_path)


def test_atomic_interruption_preserves_original(tmp_path, monkeypatch):
    from robust_budget_allocation.io import atomic
    destination = tmp_path / "record.json"
    atomic_write_json(destination, {"old": True})
    def failure(*args):
        raise OSError("injected interrupted replace")
    monkeypatch.setattr(atomic.os, "replace", failure)
    with pytest.raises(OSError):
        atomic_write_json(destination, {"new": True})
    assert json.loads(destination.read_text()) == {"old": True}


def test_watchdog_timeout_preserves_logs(tmp_path):
    outcome = supervise([sys.executable, "-c", "import time; print('started', flush=True); time.sleep(10)"],
                        tmp_path, dict(startup=.2, algorithm=.2, postprocess=.2))
    assert outcome["status"] == "time_limit"
    assert outcome["exit_code"] != 0
    assert (tmp_path / "stdout.txt").is_file()


def test_worker_crash_exit_is_not_success(tmp_path):
    outcome = supervise([sys.executable, "-c", "raise SystemExit(7)"], tmp_path,
                        dict(startup=5, algorithm=5, postprocess=5))
    assert outcome["exit_code"] == 7
    assert inspect_run(tmp_path) == "incomplete"


def test_peak_memory_is_positive_or_explicitly_unavailable():
    peak = peak_rss()
    assert peak is None or peak > 0


def test_source_gate_scopes_executable_package_not_packaging_metadata(monkeypatch):
    from robust_budget_allocation.pilot import execution
    captured = {}
    def gate(root, **kwargs):
        captured.update(kwargs)
        return {"tracked_dirty": False}
    monkeypatch.setattr(execution, "validate_source_state", gate)
    execution.source_gate()
    assert captured["scientific_roots"] == ("src/robust_budget_allocation", "tests", "scripts", "configs")
    assert all("egg-info" not in str(p) for p in captured["required_tracked_paths"])


@pytest.mark.gurobi
@pytest.mark.parametrize("method", ["M0", "M1"])
def test_ablation_adapter_existing_development_fixture(method):
    # This is a pre-existing N5 development case, never one of the new pilot configs.
    from robust_budget_allocation.data.mechanism_data import OptionData
    from robust_budget_allocation.runtime.environment import ensure_preflight_once
    ensure_preflight_once()
    cases = json.loads((ROOT / "tests/fixtures/n5_correctness.json").read_text(encoding="utf-8"))["cases"]
    data = OptionData.from_dict(cases[0]["data"])
    result = solve_ablation(data, method)
    assert result["status"] == "optimal"
    assert verify_ablation(data, result)
    assert result["first_stage"]["y_F"] == 0
