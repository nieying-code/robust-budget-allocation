"""N7-pre bounded serial diagnostic execution; no N6 mutation or result reuse."""

import json
import os
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

from robust_budget_allocation.algorithms.common import settings
from robust_budget_allocation.algorithms.extensive_form import solve_extensive_form
from robust_budget_allocation.algorithms.standard_ccg import solve_a0
from robust_budget_allocation.algorithms.memory_guided_ccg import solve_a1
from robust_budget_allocation.algorithms.verification import verify_pair
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.io.locking import exclusive_file_lock
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from robust_budget_allocation.pilot.execution import supervise, utc
from robust_budget_allocation.pilot.heartbeat import GROUPS, exception_context
from robust_budget_allocation.pilot.measurement import solve_ablation, verify_engine, metrics, mechanism
from robust_budget_allocation.pilot.storage import reserve, seal, check_seal, file_manifest, read_run, normalize_failure
from robust_budget_allocation.pilot.replay import verify_environment
from .configuration import ROOT, FROZEN, SCOPE, generate, binding, registration, order
from .audit import inputs, source, same, proof, verify_source, verify_gate, save_archive
from .replay import replay_run, replay_group, replay_bundle
from .diagnosis import summarize, option_gate

BATCH = "n7pre01"
OUTPUT = ROOT / "outputs/n7_pre" / BATCH
GATES = ROOT / "outputs/harness-validation/n7-pre-v1"


def gates():
    registration()
    before = source()
    GATES.mkdir(parents=True, exist_ok=False)
    payload = dict(classification=SCOPE, status="FAIL", source=before, frozen_hashes=FROZEN, suites={}, xml_files={}, started_utc=utc())
    try:
        for name, selection in (("solver-free", "not gurobi"), ("licensed", "gurobi")):
            xml = GATES / (name+".xml")
            result = subprocess.run([sys.executable, "-m", "pytest", "-m", selection, "-q", "--junitxml", str(xml)], cwd=ROOT)
            suites = list(ET.parse(xml).getroot().iter("testsuite"))
            counts = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
            payload["suites"][name] = dict(**counts, returncode=result.returncode, xml_sha256=sha256_file(xml))
            payload["xml_files"][name] = xml.read_bytes().decode("utf-8")
            if result.returncode or counts["failures"] or counts["errors"] or not counts["tests"] or (name == "licensed" and counts["skipped"]):
                raise RuntimeError("N7-pre gate failed: "+name)
        payload["environment"] = ensure_preflight_once().to_dict()
        verify_environment(payload["environment"])
        if not same(source(), before):
            raise ValueError("source changed during gates")
        payload.update(status="PASS", git_objects=proof(before))
        verify_source(before, payload["git_objects"])
    except BaseException as exc:
        payload["status"] = "FAIL"
        payload["exception"] = exception_context(exc, stage="gates", heartbeat=None, elapsed=0)
    payload["finished_utc"] = utc()
    atomic_write_json(GATES / "gates.json", seal(payload))
    if payload["status"] == "PASS":
        validate_gates()  # Real persisted JSON/source validation before any science.
    print(json.dumps(dict(gate_status=payload["status"], suites=payload["suites"])), flush=True)
    return 0 if payload["status"] == "PASS" else 1


def validate_gates():
    gate = json.loads((GATES / "gates.json").read_text(encoding="utf-8"))
    verify_gate(gate, source())
    for name, row in gate["suites"].items():
        if sha256_file(GATES / (name+".xml")) != row["xml_sha256"]:
            raise ValueError("gate XML hash")
    return gate


def worker(folder):
    if folder.resolve().parent != OUTPUT.resolve() or any((folder/n).exists() for n in ("result.json", "record.json", "manifest.json")):
        raise ValueError("worker folder scope/overwrite")
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    check_seal(request)
    if request["classification"] != SCOPE or request["batch_id"] != BATCH or request["solver_config"] != settings():
        raise ValueError("worker scope/settings")
    claim = json.loads((OUTPUT / "batch_start.json").read_text(encoding="utf-8"))
    check_seal(claim)
    gate = validate_gates()
    if not same(request["source"], gate["source"]) or not same(claim["source"], gate["source"]):
        raise ValueError("worker source outside batch")
    index = registration()["configs"].index(request["config"])
    if request["run_id"] != f"{BATCH}-{index:02d}-{request['method'].lower()}" or request["method"] not in order(index):
        raise ValueError("worker identity")
    if index >= 18:
        layer = json.loads((OUTPUT / "layer1_gate.json").read_text(encoding="utf-8"))
        check_seal(layer)
        if layer["gate"]["status"] != "N7_PRE_OPTION_GATE_PASSED" or not same(layer["source"], gate["source"]):
            raise ValueError("Layer2 not authorized")
    starts, timing, environment, engine = {}, {}, None, None
    def event(stage):
        starts.setdefault(GROUPS[stage], perf_counter())
        atomic_write_json(folder / "heartbeat.json", dict(run_id=request["run_id"], stage=stage, pid=os.getpid(),
                         utc=utc(), phase_started_monotonic=starts[GROUPS[stage]]))
    try:
        event("preflight")
        start = perf_counter()
        environment = ensure_preflight_once().to_dict()
        timing["preflight_seconds"] = perf_counter()-start
        event("construction")
        start = perf_counter()
        data = generate(request["config"])
        if binding(request["config"], data) != request["binding"]:
            raise ValueError("worker data binding")
        timing["construction_seconds"] = perf_counter()-start
        event("algorithm")
        start = perf_counter()
        method = request["method"]
        if method in ("M0", "M1"):
            engine = solve_ablation(data, method)
        elif method == "EF":
            engine = solve_extensive_form(data, audit_inputs=inputs())
        else:
            engine = (solve_a0 if method == "A0" else solve_a1)(data, max_iterations=13, audit_inputs=inputs())
        timing["call_envelope_seconds"] = perf_counter()-start
        event("verification")
        status = normalize_failure(engine["status"])
        start = perf_counter()
        if status == "success/certified":
            verify_engine(data, engine)
        timing["verification_seconds"] = perf_counter()-start
        if not same(source(), request["source"]):
            raise ValueError("source changed during worker")
        result = dict(status=status, engine=engine, metrics=metrics(engine) if status == "success/certified" else None,
                      mechanism=mechanism(data, engine) if status == "success/certified" else None)
    except BaseException as exc:
        result = dict(status="verification_failure" if isinstance(exc, (ValueError, KeyError, ArithmeticError)) else "solver_error",
                      engine=engine, metrics=None, mechanism=None,
                      exception=exception_context(exc, stage="worker", heartbeat=None, elapsed=0))
    result.update(classification=SCOPE, run_id=request["run_id"], environment=environment,
                  timing=timing, solver_config=settings(), finished_utc=utc())
    start = perf_counter()
    atomic_write_json(folder / "result.json", seal(result, "result_sha256"))
    timing_serialization = perf_counter()-start
    event("complete")
    heartbeat = json.loads((folder / "heartbeat.json").read_text(encoding="utf-8"))
    heartbeat["result_serialization_seconds"] = timing_serialization
    atomic_write_json(folder / "heartbeat.json", heartbeat)
    return 0 if result["status"] == "success/certified" else 1


def run_one(config, method, index, expected_source):
    if not same(source(), expected_source):
        raise ValueError("batch source changed")
    data = generate(config)
    run_id = f"{BATCH}-{index:02d}-{method.lower()}"
    with reserve(OUTPUT, run_id) as folder:
        request = seal(dict(classification=SCOPE, run_id=run_id, method=method, config=config,
            binding=binding(config, data), source=expected_source, batch_id=BATCH, solver_config=settings(), started_utc=utc()))
        atomic_write_json(folder / "request.json", request)
        atomic_write_json(folder / "heartbeat.json", dict(run_id=run_id, stage="startup", utc=utc()))
        watch = supervise([sys.executable, str(ROOT / "scripts/n7_pre.py"), "worker", "--folder", str(folder)],
                          folder, registration()["limits"])
        if not (folder / "result.json").exists():
            atomic_write_json(folder / "result.json", seal(dict(run_id=run_id, status="incomplete", engine=None,
                metrics=None, environment=None, classification=SCOPE), "result_sha256"))
        try:
            result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            result = dict(status="incomplete")
        status = watch["status"] or result["status"]
        if watch["diagnostic"] == "worker exited without complete supervised outcome" and result["status"] != "success/certified":
            status = result["status"]
        if watch["exit_code"] != 0 and status == "success/certified":
            status = "incomplete"
        record = {k: request[k] for k in ("classification", "run_id", "method", "config", "binding", "source", "batch_id", "started_utc")}
        record.update(status=status, certified=status == "success/certified", retry_reason=None, parent_run_id=None,
            watchdog=watch, environment=result.get("environment"), metrics=result.get("metrics"), finished_utc=utc(),
            trace_sha256=canonical_json_sha256((result.get("engine") or {}).get("trace", [])))
        atomic_write_json(folder / "record.json", seal(record, "output_sha256"))
        for name in ("stdout.txt", "stderr.txt"):
            if not (folder/name).exists(): (folder/name).touch(exist_ok=False)
        file_manifest(folder)
        return read_run(folder)


def execute():
    gate = validate_gates()
    with exclusive_file_lock(ROOT / "outputs/n7_pre/.locks/n7pre01.lock", timeout_seconds=0):
        OUTPUT.mkdir(parents=True, exist_ok=False)
        atomic_write_json(OUTPUT / "batch_start.json", seal(dict(source=gate["source"], batch_id=BATCH, started_utc=utc())))
        runs, observations, failure = [], [], None
        for index, config in enumerate(registration()["configs"]):
            group = []
            try:
                for method in order(index):
                    saved = run_one(config, method, index, gate["source"])
                    runs.append(saved)
                    row = replay_run(saved, gate["source"])
                    print(json.dumps(dict(run_id=row["record"]["run_id"], status=row["record"]["status"])), flush=True)
                    if row["replay"] != "PASS":
                        failure = dict(run_id=row["record"]["run_id"], status=row["record"]["status"])
                        break
                    group.append(saved)
                    if method == "A0":
                        ef = json.loads(group[2]["files"]["result.json"])["engine"]
                        verify_pair(generate(config), ef, row["result"]["engine"])
                if failure: break
                observations.append(replay_group(group, gate["source"]))
                if index == 17:
                    decision = option_gate(observations)
                    atomic_write_json(OUTPUT / "layer1_gate.json", seal(dict(gate=decision, source=gate["source"],
                        evidence_hash=canonical_json_sha256(observations))))
                    print(json.dumps(decision), flush=True)
                    if decision["status"] != "N7_PRE_OPTION_GATE_PASSED": break
            except BaseException as exc:
                failure = dict(config_id=config["id"], status="verification_failure",
                    exception=exception_context(exc, stage="execution/replay", heartbeat=None, elapsed=0))
                break
        bundle = dict(classification=SCOPE, frozen_hashes=FROZEN, source=gate["source"], git_objects=gate["git_objects"],
            gates=gate, runs=runs, observations=observations, summary=summarize(observations), failure=failure,
            status="PASS" if failure is None else "FAIL", finished_utc=utc())
        try:
            if not same(source(), gate["source"]): raise ValueError("final source changed")
            replay_bundle(seal(bundle, "evidence_sha256"))
        except BaseException as exc:
            detail = dict(status="verification_failure",
                exception=exception_context(exc, stage="final replay", heartbeat=None, elapsed=0))
            bundle.update(status="FAIL", final_replay_failure=detail)
            if bundle["failure"] is None: bundle["failure"] = detail
        save_archive(OUTPUT / "evidence.json.gz", seal(bundle, "evidence_sha256"))
        print(json.dumps(dict(status=bundle["status"], runs=len(runs), summary=bundle["summary"], failure=bundle["failure"])), flush=True)
        return 0 if bundle["status"] == "PASS" else 1
