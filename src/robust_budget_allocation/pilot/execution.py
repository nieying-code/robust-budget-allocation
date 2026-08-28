"""Serial N6 supervisor and isolated workers with immutable failure evidence."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
from time import perf_counter, sleep
import tracemalloc

from robust_budget_allocation.algorithms.common import settings
from robust_budget_allocation.algorithms.extensive_form import solve_extensive_form
from robust_budget_allocation.algorithms.standard_ccg import solve_a0
from robust_budget_allocation.algorithms.memory_guided_ccg import solve_a1
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from .configuration import ROOT, PROTOCOL, CONFIG_PATH, SCOPE, generate, binding, registration
from .measurement import solve_ablation, verify_engine, metrics, mechanism
from .storage import reserve, seal, file_manifest, normalize_failure, safe_id, retry_lineage
from .heartbeat import HeartbeatWatch, GROUPS, exception_context


def utc():
    return datetime.now(timezone.utc).isoformat()


def source_inputs():
    return sorted([*ROOT.glob("src/robust_budget_allocation/**/*.py"),
                   ROOT / "scripts/n6_pilot.py", ROOT / PROTOCOL, ROOT / CONFIG_PATH,
                   ROOT / "docs/N4_CORRECTNESS_PROTOCOL.md", ROOT / "docs/N5_A1_PROTOCOL.md",
                   ROOT / "docs/N6_HARNESS_REPAIR_AUTHORIZATION.md",
                   ROOT / "pyproject.toml", ROOT / "requirements.txt"])


def source_gate():
    return validate_source_state(ROOT, required_tracked_paths=source_inputs(),
                                 scientific_roots=("src/robust_budget_allocation", "tests", "scripts", "configs"))


def peak_rss():
    """Process lifetime native peak; distinct from call-only Python allocation peak."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        *[(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                          "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                          "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        ok = query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return int(counters.PeakWorkingSetSize) if ok else None
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value*1024)
    except ImportError:
        return None


def worker(folder):
    if any((folder / name).exists() for name in ("result.json", "record.json", "manifest.json")):
        raise FileExistsError("worker cannot overwrite an existing run")
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    if request.get("purpose") != "harness_diagnostic_only":
        raise PermissionError("full pilot worker execution is not authorized")
    started, engine = utc(), None
    timing, environment = {}, None
    phase_starts = {}

    def event(stage):
        group = GROUPS[stage]
        phase_starts.setdefault(group, perf_counter())
        atomic_write_json(folder / "heartbeat.json", dict(run_id=request["run_id"],
                           pid=os.getpid(), stage=stage, utc=utc(),
                           phase_started_monotonic=phase_starts[group]))

    try:
        event("preflight")
        source = source_gate()
        for key in ("commit_sha", "tree_sha"):
            if source[key] != request["source"]["git"][key]:
                raise RuntimeError("source changed before worker")
        start = perf_counter()
        environment = ensure_preflight_once().to_dict()
        timing["preflight_seconds"] = perf_counter()-start
        event("construction")
        start = perf_counter()
        data = generate(request["config"])
        if binding(request["config"], data) != request["binding"]:
            raise ValueError("request data/config binding")
        timing["construction_seconds"] = perf_counter()-start
        method = request["method"]
        event("algorithm")
        tracemalloc.start()
        start = perf_counter()
        if method in ("M0", "M1"):
            engine = solve_ablation(data, method)
        elif method == "EF":
            engine = solve_extensive_form(data, audit_inputs=source_inputs())
        else:
            solve = solve_a0 if method == "A0" else solve_a1
            engine = solve(data, max_iterations=len(data.base.scenarios)+1,
                           audit_inputs=source_inputs())
        timing["call_envelope_seconds"] = perf_counter()-start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        timing["python_call_peak_bytes"] = peak
        timing["process_lifetime_peak_rss_bytes"] = peak_rss()
        event("verification")
        start = perf_counter()
        status = normalize_failure(engine["status"])
        if status == "success/certified":
            verify_engine(data, engine)
        timing["verification_seconds"] = perf_counter()-start
        after = source_gate()
        if any(source[k] != after[k] for k in ("commit_sha", "tree_sha")):
            raise RuntimeError("source changed during execution")
        payload = dict(status=status, raw_status=engine["status"], engine=engine,
                       metrics=metrics(engine) if status == "success/certified" else None,
                       mechanism=mechanism(data, engine) if status == "success/certified" else None)
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        payload = dict(status="verification_failure", raw_status=engine.get("status") if engine else None,
                       engine=engine, metrics=None, mechanism=None, diagnostic=repr(exc))
    except Exception as exc:
        payload = dict(status="solver_error", raw_status=None, engine=engine,
                       metrics=None, mechanism=None, diagnostic=repr(exc))
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
    payload.update(run_id=request["run_id"], classification=SCOPE, timing=timing,
                   started_utc=started, finished_utc=utc(), environment=environment,
                   solver_config=settings(), max_iterations=request["config"]["scenarios"]+1)
    start = perf_counter()
    atomic_write_json(folder / "result.json", seal(payload, "result_sha256"))
    event("complete")
    atomic_write_json(folder / "heartbeat.json", dict(run_id=request["run_id"], pid=os.getpid(),
        stage="complete", utc=utc(), phase_started_monotonic=phase_starts["postprocess"],
        result_serialization_seconds=perf_counter()-start))
    return 0 if payload["status"] == "success/certified" else 1


def terminate_worker(process):
    """Terminate the owned worker tree, including Windows venv launcher children."""
    report = dict(attempted=False, pid=process.pid, strategy=None, command_returncode=None,
                  stdout=None, stderr=None, exit_code=process.poll(), success=True)
    if process.poll() is not None:
        return report
    report["attempted"] = True
    if os.name == "nt":
        report["strategy"] = "taskkill /T /F (owned PID)"
        completed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=10)
        report.update(command_returncode=completed.returncode,
                      stdout=completed.stdout.decode(errors="replace"),
                      stderr=completed.stderr.decode(errors="replace"))
        if completed.returncode and process.poll() is None:
            raise RuntimeError("could not terminate owned worker process tree")
    else:
        if getattr(process, "_n6_process_group", False):
            report["strategy"] = "SIGTERM isolated owned process group"
            os.killpg(process.pid, signal.SIGTERM)
        else:
            report["strategy"] = "terminate owned worker"
            process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    report["exit_code"] = process.returncode
    return report


def supervise(command, folder, limits):
    """No scientific fallback/retry: retain stdout/stderr and terminate on deadline."""
    start = perf_counter()
    watch, process = HeartbeatWatch(limits, start), None
    outcome = dict(status=None, diagnostic=None, exception=None)
    heartbeat = folder / "heartbeat.json"
    try:
        with (folder / "stdout.txt").open("xb") as stdout, (folder / "stderr.txt").open("xb") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=ROOT,
                                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                       start_new_session=os.name != "nt")
            process._n6_process_group = os.name != "nt"
            while True:
                now = perf_counter()
                if watch.expired(now):
                    outcome.update(status="incomplete" if watch.consecutive else "time_limit",
                                   diagnostic="absolute watchdog deadline: "+watch.stage)
                    break
                value = watch.read(heartbeat, now)
                now = perf_counter()
                if watch.conflict_exhausted(now):
                    outcome.update(status="incomplete", diagnostic="bounded heartbeat read conflict exhausted",
                                   exception=watch.latest_error)
                    break
                if watch.expired(now):
                    outcome.update(status="time_limit", diagnostic="absolute watchdog deadline: "+watch.stage)
                    break
                if value is not None and process.poll() is not None:
                    if process.returncode != 0 or value["stage"] != "complete":
                        outcome.update(status="incomplete", diagnostic="worker exited without complete supervised outcome")
                    break
                sleep(watch.delay(now))
    except BaseException as exc:
        outcome.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "incomplete",
                       diagnostic=repr(exc), exception=exception_context(exc, stage=watch.stage,
                       heartbeat=watch.last, elapsed=perf_counter()-start, path=heartbeat))
    finally:
        try:
            cleanup = terminate_worker(process) if process is not None else dict(
                attempted=False, success=True, exit_code=None, strategy="worker not launched")
        except BaseException as exc:
            cleanup = dict(attempted=True, success=False, exit_code=process.poll() if process else None,
                exception=exception_context(exc, stage=watch.stage, heartbeat=watch.last,
                                            elapsed=perf_counter()-start))
            outcome.update(status="incomplete", diagnostic="worker-tree cleanup failed")
        if outcome["exception"] is None and watch.consecutive:
            outcome["exception"] = getattr(watch, "latest_error", None)
        outcome.update(exit_code=process.poll() if process else None,
                       wall_seconds=perf_counter()-start, cleanup=cleanup, **watch.evidence())
    return outcome


def run_one(output_root, run_id, config, method, *, parent_run_id=None, retry_reason=None,
            parent_batch_id=None, purpose="pilot"):
    reg = registration()
    if method not in ("M0", "M1", "EF", "A0", "A1"):
        raise ValueError("unknown method")
    source_gate()
    data = generate(config)
    lineage = None
    if parent_batch_id is not None:
        lineage, saved_parent = retry_lineage(output_root, parent_batch_id, parent_run_id)
        parent_request = json.loads(saved_parent["files"]["request.json"])
        if (parent_request["binding"] != binding(config, data) or parent_request["method"] != method
                or parent_request["solver_config"] != settings()):
            raise ValueError("diagnostic retry changes original scientific input/settings")
    with reserve(output_root, run_id, parent_run_id=parent_run_id, retry_reason=retry_reason,
                 parent_batch_id=parent_batch_id) as folder:
        request = dict(run_id=run_id, parent_run_id=parent_run_id, retry_reason=retry_reason,
                       parent_batch_id=parent_batch_id, lineage=lineage, purpose=purpose,
                       method=method, config=config, binding=binding(config, data),
                       source=build_source_manifest(ROOT, input_paths=source_inputs()),
                       started_utc=utc(), solver_config=settings())
        atomic_write_json(folder / "request.json", request)
        atomic_write_json(folder / "heartbeat.json", dict(run_id=run_id, stage="startup", utc=utc()))
        interrupted = False
        try:
            watch = supervise([sys.executable, str(ROOT / "scripts/n6_pilot.py"),
                               "worker", "--folder", str(folder)], folder,
                              dict(startup=reg["startup_timeout_seconds"],
                                   algorithm=reg["timeout_seconds"],
                                   postprocess=reg["postprocess_timeout_seconds"]))
            interrupted = watch["status"] == "interrupted"
        except KeyboardInterrupt:
            interrupted = True
            watch = dict(status="interrupted", exit_code=None, wall_seconds=None,
                         diagnostic="supervisor interrupted; no in-place resume")
        except Exception as exc:
            watch = dict(status="incomplete", exit_code=None, wall_seconds=None, diagnostic=repr(exc))
        result_path = folder / "result.json"
        if not result_path.exists():
            atomic_write_json(result_path, seal(dict(run_id=run_id,
                status=watch["status"] or "incomplete", engine=None, metrics=None, mechanism=None,
                timing={}, environment=None, diagnostic="worker has no complete result"), "result_sha256"))
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            # Preserve malformed original bytes. Record failure, never overwrite result.
            result = dict(status="incomplete", engine=None)
        status = watch["status"] or result["status"]
        if watch["exit_code"] != 0 and status == "success/certified":
            status = "incomplete"
        record = dict(schema_version=1, classification=SCOPE, run_id=run_id,
            parent_run_id=parent_run_id, retry_reason=retry_reason, method=method,
            parent_batch_id=parent_batch_id, lineage=lineage, purpose=purpose,
            config_id=config["id"], source=request["source"], binding=request["binding"],
            started_utc=request["started_utc"], finished_utc=utc(), status=status,
            certified=status == "success/certified", watchdog=watch,
            trace_sha256=canonical_json_sha256((result.get("engine") or {}).get("trace", [])),
            metrics=result.get("metrics"), environment=result.get("environment"))
        atomic_write_json(folder / "record.json", seal(record, "output_sha256"))
        # Missing logs are explicit empty logs only if process launch itself failed.
        for name in ("stdout.txt", "stderr.txt"):
            if not (folder / name).exists():
                (folder / name).touch(exist_ok=False)
        file_manifest(folder)
        if interrupted:
            raise KeyboardInterrupt
        return folder
