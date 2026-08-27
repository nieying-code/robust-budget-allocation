"""Serial N6 supervisor and isolated workers with immutable failure evidence."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
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
from .storage import reserve, seal, file_manifest, normalize_failure, safe_id


def utc():
    return datetime.now(timezone.utc).isoformat()


def source_inputs():
    return sorted([*ROOT.glob("src/robust_budget_allocation/**/*.py"),
                   ROOT / "scripts/n6_pilot.py", ROOT / PROTOCOL, ROOT / CONFIG_PATH,
                   ROOT / "docs/N4_CORRECTNESS_PROTOCOL.md", ROOT / "docs/N5_A1_PROTOCOL.md",
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
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    started, engine = utc(), None
    timing, environment = {}, None

    def event(stage):
        atomic_write_json(folder / "heartbeat.json", dict(run_id=request["run_id"],
                           pid=os.getpid(), stage=stage, utc=utc()))

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
        stage="complete", utc=utc(), result_serialization_seconds=perf_counter()-start))
    return 0 if payload["status"] == "success/certified" else 1


def terminate_worker(process):
    """Terminate the owned worker tree, including Windows venv launcher children."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        completed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=10)
        if completed.returncode and process.poll() is None:
            raise RuntimeError("could not terminate owned worker process tree")
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def supervise(command, folder, limits):
    """No scientific fallback/retry: retain stdout/stderr and terminate on deadline."""
    start = stage_start = perf_counter()
    stage = None
    with (folder / "stdout.txt").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=ROOT,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            while process.poll() is None:
                heartbeat = folder / "heartbeat.json"
                current = json.loads(heartbeat.read_text(encoding="utf-8"))["stage"] if heartbeat.exists() else "startup"
                # Construction/preflight share one startup deadline; algorithm and postprocess separate.
                group = "algorithm" if current == "algorithm" else (
                    "postprocess" if current in ("verification", "complete") else "startup")
                if group != stage:
                    stage, stage_start = group, perf_counter()
                timeout = limits[stage]
                if perf_counter()-stage_start > timeout:
                    terminate_worker(process)
                    return dict(status="time_limit", diagnostic="external watchdog: "+stage,
                                exit_code=process.returncode, wall_seconds=perf_counter()-start)
                sleep(.05)
            return dict(status=None, exit_code=process.returncode, wall_seconds=perf_counter()-start)
        except BaseException:
            terminate_worker(process)
            raise


def run_one(output_root, run_id, config, method, *, parent_run_id=None, retry_reason=None):
    reg = registration()
    if method not in ("M0", "M1", "EF", "A0", "A1"):
        raise ValueError("unknown method")
    source_gate()
    data = generate(config)
    with reserve(output_root, run_id, parent_run_id=parent_run_id, retry_reason=retry_reason) as folder:
        request = dict(run_id=run_id, parent_run_id=parent_run_id, retry_reason=retry_reason,
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
