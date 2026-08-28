"""Fresh restart orchestration tests use fakes only, never scientific solves."""

import json
from copy import deepcopy
import pytest

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.pilot import restart as r
from robust_budget_allocation.pilot.configuration import registration, execution_order
from robust_budget_allocation.pilot.storage import seal


@pytest.mark.parametrize("batch", [None, "n6pilot01", "n6diagnostic01", "n6pilot03", "../n6pilot02"])
def test_only_fresh_fixed_batch_authorized(batch):
    with pytest.raises(PermissionError):
        r.execute(batch, lambda *a: pytest.fail("archive not authorized"))


def fake_execution(tmp_path, monkeypatch, fail_at=None, audit_at=None):
    gate_path = tmp_path / "gates.json"
    atomic_write_json(gate_path, {"test_gate": True})
    monkeypatch.setattr(r, "ROOT", tmp_path)
    monkeypatch.setattr(r, "GATE_FILE", gate_path)
    monkeypatch.setattr(r, "source_gate", lambda: {"commit_sha": "fixed", "tree_sha": "fixed"})
    monkeypatch.setattr(r, "manifest", lambda: {"source": "fixed"})
    monkeypatch.setattr(r, "validate_gates", lambda gate: None)
    calls, saved, captured = [], {}, []
    def run(root, run_id, config, method):
        index = len(calls)
        calls.append((run_id, config, method))
        row = dict(run_id=run_id, status="incomplete" if index == fail_at else "success/certified",
                   source={"source": "fixed"}, metrics={})
        folder = root / run_id
        folder.mkdir()
        saved[folder] = {"files": {"record.json": json.dumps(row)}}
        return folder
    monkeypatch.setattr(r, "run_one", run)
    monkeypatch.setattr(r, "read_run", lambda folder: saved[folder])
    def replay(saved):
        if len(calls)-1 == audit_at:
            raise ValueError("injected audit failure")
    monkeypatch.setattr(r, "replay_run", replay)
    monkeypatch.setattr(r, "replay_group", lambda group: {"PASS": True})
    monkeypatch.setattr(r, "replay_restart", lambda bundle: {"PASS": True})
    status = r.execute("n6pilot02", lambda path, payload: captured.append(payload))
    return status, calls, captured[0]


def test_all_80_follow_frozen_order_one_source_and_duplicate_refused(tmp_path, monkeypatch):
    status, calls, evidence = fake_execution(tmp_path, monkeypatch)
    expected = [(f"n6pilot02-{i:02d}-{m.lower()}", c, m)
                for i, c in enumerate(registration()["configs"]) for m in execution_order(i)]
    assert status == 0 and calls == expected and len(calls) == 80
    assert len(evidence["pair_checks"]) == 16 and evidence["status"] == "PASS"
    with pytest.raises(FileExistsError):
        r.execute("n6pilot02", lambda *a: pytest.fail("must not overwrite"))


@pytest.mark.parametrize("fault", ["status", "audit"])
def test_first_failure_stops_before_next_run(tmp_path, monkeypatch, fault):
    status, calls, evidence = fake_execution(tmp_path, monkeypatch,
        fail_at=2 if fault == "status" else None, audit_at=2 if fault == "audit" else None)
    assert status == 1 and len(calls) == 3
    assert evidence["status"] == "FAIL" and evidence["failure"] and not evidence["pair_checks"]


def test_gate_missing_or_failed_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "source_gate", lambda: {})
    monkeypatch.setattr(r, "GATE_FILE", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        r.execute("n6pilot02", lambda *a: pytest.fail("no gate"))
    with pytest.raises(ValueError, match="not passed"):
        r.validate_gates(seal(dict(status="FAIL", batch_id="n6pilot02")))


def test_worker_rejects_old_batch_and_retry(tmp_path):
    with pytest.raises(PermissionError):
        r.validate_worker(tmp_path / "n6pilot01/old", {"purpose": "pilot"})
    with pytest.raises(ValueError, match="cannot reuse"):
        r.validate_worker(r.ROOT / "outputs/pilot/n6pilot02/n6pilot02-00-m0",
                          {"purpose": "pilot", "parent_run_id": "old"})
