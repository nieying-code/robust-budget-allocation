"""One fresh registered N6 batch; no resume, retries, or historical result reuse."""

import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import sha256_file, canonical_json_bytes
from robust_budget_allocation.io.locking import exclusive_file_lock
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.runtime.environment import ensure_preflight_once
from .configuration import ROOT, registration, execution_order, PROTOCOL_SHA, CONFIG_SHA, SCOPE
from .execution import source_gate, source_inputs, run_one, utc
from .heartbeat import exception_context
from .replay import replay_run, replay_group, replay_bundle, verify_source, verify_environment
from .storage import read_run, seal, check_seal

BATCH = "n6pilot02"
GATES = ROOT / "outputs/harness-validation/n6pilot02"
GATE_FILE = GATES / "gates.json"


def manifest():
    return build_source_manifest(ROOT, input_paths=source_inputs())


def same_content(left, right):
    """Compare complete JSON-normalized contents, NOT stored digest fields.

    N1 intentionally returns tuples in its in-memory API; JSON persists arrays.
    Canonical bytes preserve every field and array order, ignore dictionary order,
    equate tuple/list representations, and reject NaN/Inf. N1 is unchanged.
    Source seals, Git-object authentication and inventory checks remain separate.
    """
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def validate_gates(gate):
    check_seal(gate)
    if gate["status"] != "PASS" or gate["batch_id"] != BATCH:
        raise ValueError("restart gates not passed")
    if not same_content(gate["source"], manifest()):
        raise ValueError("restart gate/source mismatch")
    verify_source(gate["source"])
    verify_environment(gate["environment"])
    if gate["protocol_sha256"] != PROTOCOL_SHA or gate["config_sha256"] != CONFIG_SHA:
        raise ValueError("restart gate registration mismatch")
    if set(gate["suites"]) != {"solver-free", "licensed", "windows-stress"}:
        raise ValueError("missing gate suite")
    for name, row in gate["suites"].items():
        if row["returncode"] != 0 or row["failures"] or row["errors"] or row["skipped"] or row["tests"] <= 0:
            raise ValueError("failed/skipped gate suite")
        if sha256_file(GATES / (name+".xml")) != row["xml_sha256"]:
            raise ValueError("gate XML hash")


def gates():
    """Run gates once and retain failures. No scientific batch is created here."""
    before = source_gate()
    registration()
    if os.name != "nt":
        raise RuntimeError("Windows stress gate requires Windows")
    GATES.mkdir(parents=True, exist_ok=False)
    payload = dict(batch_id=BATCH, started_utc=utc(), source=manifest(),
                   protocol_sha256=PROTOCOL_SHA, config_sha256=CONFIG_SHA,
                   status="FAIL", suites={}, environment=None)
    commands = {
        "solver-free": ["-m", "not gurobi"],
        "licensed": ["-m", "gurobi"],
        "windows-stress": ["tests/test_n6_harness_repair.py", "-k", "windows"],
    }
    try:
        for name, selection in commands.items():
            xml = GATES / (name+".xml")
            result = subprocess.run([sys.executable, "-m", "pytest", *selection, "-q", "--junitxml", str(xml)], cwd=ROOT)
            suites = ET.parse(xml).getroot().iter("testsuite")
            counts = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
            for suite in suites:
                for k in counts:
                    counts[k] += int(suite.attrib.get(k, 0))
            payload["suites"][name] = dict(**counts, returncode=result.returncode, xml_sha256=sha256_file(xml))
            if result.returncode or counts["failures"] or counts["errors"] or counts["skipped"] or not counts["tests"]:
                raise RuntimeError("engineering gate failed: "+name)
        payload["environment"] = ensure_preflight_once().to_dict()
        verify_environment(payload["environment"])
        if not same_content(source_gate(), before) or not same_content(manifest(), payload["source"]):
            raise RuntimeError("source changed during gates")
        payload["status"] = "PASS"
    except BaseException as exc:
        payload["exception"] = exception_context(exc, stage="gates", heartbeat=None, elapsed=0)
    payload["finished_utc"] = utc()
    atomic_write_json(GATE_FILE, seal(payload))
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0 if payload["status"] == "PASS" else 1


def validate_worker(folder, request):
    root = ROOT / "outputs/pilot" / BATCH
    if Path(folder).resolve().parent != root.resolve() or request.get("purpose") != "pilot":
        raise PermissionError("only authorized fresh n6pilot02 workers")
    if any(request.get(k) is not None for k in ("parent_run_id", "parent_batch_id", "retry_reason", "lineage")):
        raise ValueError("fresh pilot cannot reuse/retry history")
    configs = registration()["configs"]
    index = configs.index(request["config"])
    if request["method"] not in execution_order(index) or request["run_id"] != f"{BATCH}-{index:02d}-{request['method'].lower()}":
        raise ValueError("fresh worker identity/order")
    claim = json.loads((root / "batch_start.json").read_text(encoding="utf-8"))
    check_seal(claim)
    if not same_content(request["source"], claim["source"]):
        raise ValueError("worker outside unique batch source")
    gate = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    validate_gates(gate)
    if claim["gates_sha256"] != sha256_file(GATE_FILE):
        raise ValueError("batch gate binding")


def execute(batch, archive):
    if batch != BATCH:
        raise PermissionError("N6_FULL_PILOT_RESUME_NOT_AUTHORIZED except fresh n6pilot02")
    before = source_gate()
    reg = registration()
    gate = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    validate_gates(gate)
    source = manifest()
    root = ROOT / "outputs/pilot" / BATCH
    with exclusive_file_lock(ROOT / "outputs/pilot/.locks/n6pilot02.lock", timeout_seconds=0):
        root.mkdir(parents=True, exist_ok=False)
        claim = seal(dict(batch_id=BATCH, source=source, source_gate=before,
                          gates_sha256=sha256_file(GATE_FILE), started_utc=utc()))
        atomic_write_json(root / "batch_start.json", claim)
        runs, checks, failure = [], {}, None
        for index, config in enumerate(reg["configs"]):
            group = []
            for method in execution_order(index):
                run_id = f"{BATCH}-{index:02d}-{method.lower()}"
                try:
                    if not same_content(manifest(), source) or not same_content(source_gate(), before):
                        raise ValueError("batch source changed before run")
                    folder = run_one(root, run_id, config, method)
                    saved = read_run(folder)
                    runs.append(saved)
                    record = json.loads(saved["files"]["record.json"])
                    print(json.dumps(dict(run_id=run_id, status=record["status"], metrics=record["metrics"])), flush=True)
                    if record["status"] != "success/certified":
                        failure = dict(run_id=run_id, status=record["status"])
                        break
                    if not same_content(record["source"], source):
                        raise ValueError("mixed batch source")
                    replay_run(saved)  # audit BEFORE the next scientific run
                    group.append(saved)
                except BaseException as exc:
                    failure = dict(run_id=run_id, status="interrupted" if isinstance(exc, KeyboardInterrupt) else "verification_failure",
                                   exception=exception_context(exc, stage="run/replay", heartbeat=None, elapsed=0))
                    break
            if failure:
                break
            try:
                checks[config["id"]] = replay_group(group)
            except BaseException as exc:
                failure = dict(config_id=config["id"], status="verification_failure",
                               exception=exception_context(exc, stage="paired replay", heartbeat=None, elapsed=0))
                break
        bare = dict(schema_version=1, classification=SCOPE, protocol_sha256=PROTOCOL_SHA,
                    config_sha256=CONFIG_SHA, source_gate=before, source=source,
                    batch_start=claim, gates=gate, batch_id=BATCH, runs=runs,
                    status="PASS" if failure is None and len(runs) == 80 else "FAIL",
                    failure=failure, pair_checks=checks)
        try:
            if not same_content(source_gate(), before) or not same_content(manifest(), source):
                raise ValueError("batch final source mismatch")
            if bare["status"] == "PASS":
                replay_restart(seal(bare, "evidence_sha256"))
        except BaseException as exc:
            bare.update(status="FAIL", failure=dict(status="verification_failure",
                exception=exception_context(exc, stage="final replay", heartbeat=None, elapsed=0)))
        evidence = seal(bare, "evidence_sha256")
        archive(root / "compact_evidence.json.gz", evidence)
        print(json.dumps(dict(status=evidence["status"], runs=len(runs), failure=evidence["failure"])), flush=True)
        return 0 if evidence["status"] == "PASS" else 1


def replay_restart(bundle):
    result = replay_bundle(bundle)
    if bundle["batch_id"] != BATCH:
        raise ValueError("restart batch identity")
    if len(bundle["runs"]) > 80:
        raise ValueError("restart has excess runs")
    if any(bundle["source"]["git"][k] != bundle["source_gate"][k] for k in ("commit_sha", "tree_sha")):
        raise ValueError("restart external source anchor")
    expected = [(f"{BATCH}-{i:02d}-{m.lower()}", c, m)
                for i, c in enumerate(registration()["configs"]) for m in execution_order(i)]
    for saved, (run_id, config, method) in zip(bundle["runs"], expected, strict=False):
        row = json.loads(saved["files"]["record.json"])
        if row["run_id"] != run_id or row["binding"]["config"] != config or row["method"] != method:
            raise ValueError("restart run order/identity")
        if not same_content(row["source"], bundle["source"]) or row.get("purpose") != "pilot":
            raise ValueError("restart mixed source/purpose")
        if any(row.get(k) is not None for k in ("parent_run_id", "parent_batch_id", "retry_reason", "lineage")):
            raise ValueError("restart reuses historical run")
    check_seal(bundle["batch_start"])
    check_seal(bundle["gates"])
    if not same_content(bundle["batch_start"]["source"], bundle["source"]) or not same_content(bundle["gates"]["source"], bundle["source"]):
        raise ValueError("restart gate source")
    if bundle["gates"]["status"] != "PASS":
        raise ValueError("restart gates failed")
    gate = bundle["gates"]
    if gate["batch_id"] != BATCH or gate["protocol_sha256"] != PROTOCOL_SHA or gate["config_sha256"] != CONFIG_SHA:
        raise ValueError("restart gate registration")
    verify_environment(gate["environment"])
    if set(gate["suites"]) != {"solver-free", "licensed", "windows-stress"}:
        raise ValueError("restart gate suites missing")
    for suite in gate["suites"].values():
        if suite["returncode"] or suite["failures"] or suite["errors"] or suite["skipped"] or suite["tests"] <= 0:
            raise ValueError("restart gate suite not passed")
    return result
