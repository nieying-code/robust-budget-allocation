"""Authorized harness repair tests; stress/fault probes are not scientific runs."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, sleep

import pytest

from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.locking import exclusive_file_lock
from robust_budget_allocation.pilot.heartbeat import HeartbeatWatch
from robust_budget_allocation.pilot import heartbeat as hb
from robust_budget_allocation.pilot.execution import supervise, terminate_worker, worker
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.storage import reserve, retry_lineage, seal, read_run
from robust_budget_allocation.pilot.replay import load_bundle, verify_source, replay_group
from robust_budget_allocation.pilot.diagnostic import claim_once, PARENT_ID, PARENT_BATCH, REASON

LIMITS = dict(startup=10., algorithm=20., postprocess=10.)


@pytest.mark.parametrize("error", [PermissionError(13, "sharing conflict", "heartbeat.json"),
                                  FileNotFoundError(2, "rename race", "heartbeat.json")])
def test_transient_read_recovers_using_last_stage_without_reset(tmp_path, monkeypatch, error):
    path = tmp_path / "heartbeat.json"
    atomic_write_json(path, dict(stage="algorithm", phase_started_monotonic=2))
    watch = HeartbeatWatch(LIMITS, 0)
    watch.read(path, 3)
    deadline = watch.deadline
    original = hb.read_text_shared
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(hb, "read_text_shared", fail)
    assert watch.read(path, 3.02) is None
    assert watch.stage == "algorithm" and watch.last["stage"] == "algorithm"
    assert watch.deadline == deadline == 22
    assert not watch.conflict_exhausted(3.03)
    monkeypatch.setattr(hb, "read_text_shared", original)
    watch.read(path, 3.04)
    assert watch.deadline == deadline and watch.recovered_windows == 1
    context = watch.errors[0]
    assert context["errno"] in (2, 13) and context["filename"] == "heartbeat.json"
    assert "read" in context["traceback"] and context["last_valid_heartbeat"]["stage"] == "algorithm"


def test_retry_cannot_extend_deadline_or_delayed_phase_start(tmp_path, monkeypatch):
    path = tmp_path / "heartbeat.json"
    atomic_write_json(path, dict(stage="startup", phase_started_monotonic=0))
    watch = HeartbeatWatch(dict(startup=1., algorithm=2., postprocess=1.), 0)
    watch.read(path, .1)
    original = hb.read_text_shared
    def denied(*args, **kwargs):
        raise PermissionError(13, "locked", str(path))
    monkeypatch.setattr(hb, "read_text_shared", denied)
    watch.read(path, .98)
    assert watch.delay(.99) <= .011
    assert watch.expired(1.) and watch.conflict_exhausted(1.)
    assert watch.deadlines == {"startup": 1.}
    monkeypatch.setattr(hb, "read_text_shared", original)
    # Independently exercise delayed observation of an ORIGINAL phase timestamp.
    watch = HeartbeatWatch(LIMITS, 0)
    atomic_write_json(path, dict(stage="algorithm", phase_started_monotonic=1.))
    watch.read(path, 4.)
    assert watch.deadline == 21.  # NOT receipt(4)+20
    atomic_write_json(path, dict(stage="algorithm", phase_started_monotonic=7.))
    watch.read(path, 8.)
    assert watch.deadline == 21.  # repeated stage cannot reset


@pytest.mark.parametrize("error", [ValueError("bad json"), OSError(5, "nontransient I/O")])
def test_other_read_failures_are_not_retried(tmp_path, monkeypatch, error):
    def broken(*args, **kwargs):
        raise error
    monkeypatch.setattr(hb, "read_text_shared", broken)
    watch = HeartbeatWatch(LIMITS, 0)
    with pytest.raises(type(error)):
        watch.read(tmp_path / "heartbeat.json", 1.)
    assert watch.total_conflicts == 0


def test_persistent_read_conflict_bounded_and_detailed(tmp_path, monkeypatch):
    atomic_write_json(tmp_path / "heartbeat.json", {"stage": "startup"})
    def denied(*args, **kwargs):
        exc = PermissionError(13, "locked", str(tmp_path / "heartbeat.json"))
        exc.winerror = 32
        raise exc
    monkeypatch.setattr(hb, "read_text_shared", denied)
    result = supervise([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, LIMITS)
    assert result["status"] == "incomplete" and result["total_read_conflicts"] == 8
    assert result["cleanup"]["success"] and result["cleanup"]["attempted"]
    assert result["exit_code"] == result["cleanup"]["exit_code"] and result["exit_code"] is not None
    context = result["exception"]
    assert context["exception_type"] == "PermissionError" and context["errno"] == 13 and context["winerror"] == 32
    assert context["filename"].endswith("heartbeat.json") and context["requested_path"].endswith("heartbeat.json")
    assert context["stage"] == "startup" and context["traceback"] and context["wall_seconds"] >= 0
    assert result["wall_seconds"] < 10


def test_recovered_conflict_does_not_hide_live_watchdog(tmp_path, monkeypatch):
    path = tmp_path / "heartbeat.json"
    atomic_write_json(path, {"stage": "startup"})
    original, count = hb.read_text_shared, 0
    def flaky(file, *args, **kwargs):
        nonlocal count
        count += 1
        if file == path and count <= 3:
            raise FileNotFoundError(2, "transient", str(file))
        return original(file, *args, **kwargs)
    monkeypatch.setattr(hb, "read_text_shared", flaky)
    result = supervise([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path,
                       dict(startup=.4, algorithm=1., postprocess=1.))
    assert result["status"] == "time_limit" and result["total_read_conflicts"] == 3
    assert result["recovered_conflict_windows"] == 1
    assert result["cleanup"]["success"]


def test_worker_refuses_existing_directory_before_any_write(tmp_path):
    atomic_write_json(tmp_path / "record.json", {"old": "must remain unchanged"})
    before = (tmp_path / "record.json").read_bytes()
    with pytest.raises(FileExistsError):
        worker(tmp_path)
    assert (tmp_path / "record.json").read_bytes() == before
    assert not (tmp_path / "heartbeat.json").exists()


def parent_fixture(root):
    saved = next(r for r in load_bundle(ROOT / "docs/evidence/N6_PILOT_EVIDENCE.json.gz")["runs"]
                 if json.loads(r["files"]["record.json"])["run_id"] == PARENT_ID)
    folder = root / PARENT_BATCH / PARENT_ID
    for name, text in saved["files"].items():
        atomic_write_text(folder / name, text)
    atomic_write_json(folder / "manifest.json", saved["manifest"])
    return folder, saved


def test_cross_batch_lineage_and_parent_immutability(tmp_path):
    folder, saved = parent_fixture(tmp_path)
    root = tmp_path / "newbatch"
    lineage, copied = retry_lineage(root, PARENT_BATCH, PARENT_ID)
    assert copied == saved
    assert lineage["parent_relative_path"] == PARENT_BATCH+"/"+PARENT_ID
    assert lineage["parent_manifest_sha256"] == saved["manifest"]["sha256"]
    with reserve(root, "newid", parent_run_id=PARENT_ID, parent_batch_id=PARENT_BATCH, retry_reason=REASON):
        pass
    assert read_run(folder) == saved
    with pytest.raises(FileExistsError):
        with reserve(root, "newid", parent_run_id=PARENT_ID, parent_batch_id=PARENT_BATCH, retry_reason=REASON):
            pass
    with pytest.raises(ValueError):
        retry_lineage(root, "../escape", PARENT_ID)


def test_authorization_claim_is_single_use_even_without_a_result(tmp_path):
    claim = claim_once(tmp_path, {"test": "no solver"})
    assert claim["parent_run_id"] == PARENT_ID and claim["retry_reason"] == REASON
    with pytest.raises(FileExistsError, match="already consumed"):
        claim_once(tmp_path, {"test": "cannot launch twice"})


def test_full_pilot_cli_is_disabled():
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/n6_pilot.py"), "run", "--batch", "not-authorized"],
                               capture_output=True, text=True)
    assert completed.returncode != 0 and "N6_FULL_PILOT_RESUME_NOT_AUTHORIZED" in completed.stderr
    assert not (ROOT / "outputs/pilot/not-authorized").exists()


def test_historical_source_authentication_and_forged_anchor():
    saved = load_bundle(ROOT / "docs/evidence/N6_PILOT_EVIDENCE.json.gz")["runs"][0]
    source = json.loads(saved["files"]["record.json"])["source"]
    verify_source(source)
    forged = deepcopy(source)
    forged["git"]["tree_sha"] = "0"*40
    forged.pop("manifest_sha256")
    forged = seal(forged, "manifest_sha256")
    with pytest.raises(ValueError, match="commit/tree"):
        verify_source(forged)


def test_shallow_checkout_source_proof_and_tamper_rejection(monkeypatch):
    from robust_budget_allocation.pilot import source_archive as archive
    source = json.loads(load_bundle(ROOT / "docs/evidence/N6_PILOT_EVIDENCE.json.gz")["runs"][0]["files"]["record.json"])["source"]
    expected = {r["path"]: r["sha256"] for r in source["inputs"]}
    objects = deepcopy(archive.archive_objects())
    monkeypatch.setattr(archive.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"missing"))
    assert archive.authenticate_inputs(source["git"]["commit_sha"], source["git"]["tree_sha"]) == expected
    blob = next(oid for oid, item in objects.items() if item["kind"] == "blob")
    objects[blob]["base64"] = "Zm9yZ2Vk"
    monkeypatch.setattr(archive, "archive_objects", lambda: objects)
    with pytest.raises(ValueError, match="object hash"):
        archive.authenticate_inputs(source["git"]["commit_sha"], source["git"]["tree_sha"])


def test_cross_source_scientific_group_stays_rejected(monkeypatch):
    from robust_budget_allocation.pilot import replay
    base = dict(binding={}, environment={}, source={"git": {"commit_sha": "old"}}, purpose="pilot")
    decoded = [dict(record={**deepcopy(base), "method": m}, replay="PASS") for m in ("M0", "M1", "EF", "A0", "A1")]
    decoded[2]["record"]["source"] = {"git": {"commit_sha": "new"}}
    monkeypatch.setattr(replay, "replay_run", lambda i: decoded[i])
    with pytest.raises(ValueError, match="unpaired source"):
        replay_group(list(range(5)))
    decoded[2]["record"]["purpose"] = "harness_diagnostic_only"
    with pytest.raises(ValueError, match="cannot be pooled"):
        replay_group(list(range(5)))


@pytest.mark.skipif(os.name != "nt", reason="actual Windows sharing and venv process-tree stress")
@pytest.mark.parametrize("repetition", range(3))
def test_windows_high_frequency_atomic_heartbeat(tmp_path, repetition, record_property):
    script = """
import sys,time
from pathlib import Path
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.locking import exclusive_file_lock
folder=Path(sys.argv[1])
start=time.perf_counter()
with exclusive_file_lock(folder/'writer.lock',timeout_seconds=0):
    n=0
    while time.perf_counter()-start < 10:
        atomic_write_json(folder/'heartbeat.json',dict(stage='algorithm',phase_started_monotonic=start,sequence=n))
        n+=1
    atomic_write_json(folder/'heartbeat.json',dict(stage='complete',phase_started_monotonic=time.perf_counter(),sequence=n))
"""
    started = perf_counter()
    atomic_write_json(tmp_path / "heartbeat.json", {"stage": "startup"})
    watch = HeartbeatWatch(dict(startup=10., algorithm=30., postprocess=10.), started)
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reads = 0
    try:
        while process.poll() is None:
            watch.read(tmp_path / "heartbeat.json", perf_counter())
            reads += 1
            assert not watch.conflict_exhausted(perf_counter())
            assert not watch.expired(perf_counter())
            sleep(min(.001, watch.delay(perf_counter())))
        assert process.returncode == 0, process.stderr.read().decode(errors="replace")
        watch.read(tmp_path / "heartbeat.json", perf_counter())
        assert watch.last["stage"] == "complete" and watch.last["sequence"] >= 50
        assert reads > 100
    finally:
        cleanup = terminate_worker(process)
    with exclusive_file_lock(tmp_path / "writer.lock", timeout_seconds=0):
        pass
    record_property("windows_stress", json.dumps(dict(repetition=repetition, writes=watch.last["sequence"]+1,
        reads=reads, conflicts=watch.total_conflicts, recovered=watch.recovered_windows,
        exit_code=process.returncode, lock_released=True, elapsed=perf_counter()-started)))


def test_cleanup_kills_grandchild_holding_lease(tmp_path, monkeypatch):
    atomic_write_json(tmp_path / "heartbeat.json", {"stage": "startup"})
    grandchild = """
import sys,time
from pathlib import Path
from robust_budget_allocation.io.locking import exclusive_file_lock
with exclusive_file_lock(Path(sys.argv[1])/'descendant.lock',timeout_seconds=0):
    print('ready',flush=True)
    time.sleep(30)
"""
    parent = """
import subprocess,sys,time
from pathlib import Path
from robust_budget_allocation.io.atomic import atomic_write_json
p=subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1]],stdout=subprocess.PIPE,text=True)
assert p.stdout.readline().strip()=='ready'
atomic_write_json(Path(sys.argv[1])/'tree-ready.json',dict(pid=p.pid))
time.sleep(30)
"""
    original = hb.read_text_shared
    def denied_after_tree_ready(path, *args, **kwargs):
        if path == tmp_path / "heartbeat.json" and (tmp_path / "tree-ready.json").exists():
            raise PermissionError(13, "injected read conflict after grandchild creation", str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(hb, "read_text_shared", denied_after_tree_ready)
    result = supervise([sys.executable, "-c", parent, str(tmp_path), grandchild], tmp_path, LIMITS)
    assert result["status"] == "incomplete" and result["cleanup"]["success"]
    assert (tmp_path / "tree-ready.json").is_file()
    with exclusive_file_lock(tmp_path / "descendant.lock", timeout_seconds=1):
        pass


@pytest.mark.skipif(os.name != "nt", reason="real Win32 sharing violation")
def test_real_windows_exclusive_handle_conflict_recovers(tmp_path):
    import ctypes
    from ctypes import wintypes
    path = tmp_path / "heartbeat.json"
    atomic_write_json(path, {"stage": "startup"})
    watch = HeartbeatWatch(LIMITS, perf_counter())
    watch.read(path, perf_counter())
    deadline = watch.deadline
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        assert watch.read(path, perf_counter()) is None
        assert watch.errors[-1]["winerror"] == 32
        assert watch.errors[-1]["exception_type"] == "PermissionError"
        assert watch.errors[-1]["filename"] == str(path)
    finally:
        kernel.CloseHandle(handle)
    assert watch.read(path, perf_counter())["stage"] == "startup"
    assert watch.recovered_windows == 1 and watch.deadline == deadline
