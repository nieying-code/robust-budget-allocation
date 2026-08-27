"""Solver-free N6 bundle replay: metadata, accounting, N4/N5 traces and pairs."""

import gzip
import hashlib
import json
import math
import subprocess
from pathlib import Path
from functools import lru_cache

from robust_budget_allocation.algorithms.a1_verification import verify_three
from robust_budget_allocation.algorithms.common import equal, upper, settings
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from .configuration import ROOT, SCOPE, METHODS, PROTOCOL_SHA, CONFIG_SHA, registration, generate, binding
from .measurement import verify_engine, mechanism, metrics
from .storage import check_seal, verify_inventory, safe_id, safe_relative, FAILURE_STATES


@lru_cache(maxsize=None)
def anchored_inputs(commit, tree):
    """Authenticate immutable historical source, never silently substitute current files."""
    from .source_archive import authenticate_inputs
    return authenticate_inputs(commit, tree)


def verify_source(source):
    check_seal(source, "manifest_sha256")
    git = source["git"]
    if git["tracked_dirty"] or any(len(git[k]) != 40 or any(c not in "0123456789abcdef" for c in git[k])
                                 for k in ("commit_sha", "tree_sha")):
        raise ValueError("dirty/invalid source anchor")
    entries = source["inputs"]
    paths = [safe_relative(e["path"]) for e in entries]
    expected = anchored_inputs(git["commit_sha"], git["tree_sha"])
    if len(paths) != len(set(paths)) or set(paths) != set(expected):
        raise ValueError("source inventory mismatch")
    for entry in entries:
        if expected[entry["path"]] != entry["sha256"]:
            raise ValueError("source hash mismatch")


def verify_environment(environment):
    expected = dict(python="3.12.10", python_implementation="CPython", pyomo="6.10.1",
        gurobipy="13.0.2", gurobi_optimizer="13.0.2", solver_interface="gurobi_direct",
        threads=1, solver_available=True, license_available=True, status="PASS")
    if any(environment.get(k) != v for k, v in expected.items()):
        raise ValueError("locked environment mismatch")


def replay_run(bundle):
    verify_inventory(bundle["manifest"], bundle["files"])
    files = bundle["files"]
    request, record = (json.loads(files[n]) for n in ("request.json", "record.json"))
    check_seal(record, "output_sha256")
    safe_id(record["run_id"])
    for key in ("run_id", "parent_run_id", "retry_reason", "method", "source", "binding"):
        if record[key] != request[key]:
            raise ValueError("request/record binding: " + key)
    for key in ("parent_batch_id", "lineage", "purpose"):
        if record.get(key) != request.get(key):
            raise ValueError("retry request/record binding: " + key)
    if record["classification"] != SCOPE or record["method"] not in METHODS:
        raise ValueError("scope/method")
    if record["config_id"] != request["config"]["id"]:
        raise ValueError("config identity")
    data = generate(request["config"])
    if request["binding"] != binding(request["config"], data):
        raise ValueError("config/scenario/data binding")
    verify_source(request["source"])
    if request["solver_config"] != settings():
        raise ValueError("solver configuration changed")
    heartbeat = json.loads(files["heartbeat.json"])
    if heartbeat["run_id"] != record["run_id"]:
        raise ValueError("heartbeat identity")
    if record["certified"] != (record["status"] == "success/certified"):
        raise ValueError("false outer certification")
    # Failed runs have integrity evidence, not a claimed mathematical certificate.
    if record["status"] != "success/certified":
        if record["status"] not in FAILURE_STATES:
            raise ValueError("unknown failure classification")
        return dict(record=record, result=None, replay="FAILURE_RETAINED")
    result = json.loads(files["result.json"])
    check_seal(result, "result_sha256")
    if result["run_id"] != record["run_id"] or result["status"] != record["status"]:
        raise ValueError("worker status mismatch")
    if heartbeat["stage"] != "complete" or record["watchdog"]["exit_code"] != 0:
        raise ValueError("incomplete worker cannot certify")
    if record.get("purpose") == "harness_diagnostic_only":
        watch = record["watchdog"]
        if watch["status"] is not None or not watch["cleanup"]["success"] or watch["cleanup"]["exit_code"] != 0:
            raise ValueError("diagnostic process cleanup not successful")
    if result["solver_config"] != settings() or result["max_iterations"] != len(data.base.scenarios)+1:
        raise ValueError("worker execution config")
    for environment in (result["environment"], record["environment"]):
        verify_environment(environment)
    if result["environment"] != record["environment"]:
        raise ValueError("outer environment")
    engine = result["engine"]
    if engine["method"] != record["method"]:
        raise ValueError("engine method")
    if "result_sha256" in engine:
        check_seal(engine, "result_sha256")
        audit = engine["audit"]
        check_seal(audit["source"], "manifest_sha256")
        if any(audit["source"]["git"][k] != record["source"]["git"][k]
               for k in ("commit_sha", "tree_sha")) or audit["source"]["git"]["tracked_dirty"]:
            raise ValueError("engine execution anchor")
        if audit["data"] != data.to_dict() or audit["data_sha256"] != data.data_sha256:
            raise ValueError("engine data")
        if audit["config_sha256"] != canonical_json_sha256(audit["config"]):
            raise ValueError("engine config hash")
        for key, value in settings().items():
            if audit["config"][key] != value:
                raise ValueError("engine solver configuration")
        verify_environment(audit["environment"])
    if record["trace_sha256"] != canonical_json_sha256(engine.get("trace", [])):
        raise ValueError("trace hash")
    verify_engine(data, engine)
    if result["metrics"] != metrics(engine) or record["metrics"] != result["metrics"]:
        raise ValueError("metrics not reconstructed")
    if result["mechanism"] != mechanism(data, engine):
        raise ValueError("mechanism/accounting not reconstructed")
    for value in result["timing"].values():
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("invalid timing/memory")
    return dict(record=record, result=result, replay="PASS")


def replay_group(runs):
    decoded = [replay_run(run) for run in runs]
    if any(d["record"].get("purpose", "pilot") != "pilot" for d in decoded):
        raise ValueError("diagnostic retry cannot be pooled into scientific configuration")
    if len(decoded) != 5 or {d["record"]["method"] for d in decoded} != set(METHODS):
        raise ValueError("paired group inventory")
    if any(d["replay"] != "PASS" for d in decoded):
        raise ValueError("failed group is not paired success")
    by_method = {d["record"]["method"]: d for d in decoded}
    first = decoded[0]["record"]
    for row in decoded:
        record = row["record"]
        if record["binding"] != first["binding"] or record["environment"] != first["environment"]:
            raise ValueError("unpaired data/environment")
        if record["source"] != first["source"]:
            raise ValueError("unpaired source")
    data = generate(first["binding"]["config"])
    engine = {m: row["result"]["engine"] for m, row in by_method.items()}
    checks = verify_three(data, engine["EF"], engine["A0"], engine["A1"])
    upper(engine["EF"]["objective"], engine["M1"]["objective"], "M2<=M1")
    upper(engine["M1"]["objective"], engine["M0"]["objective"], "M1<=M0")
    checks["paired_objective_difference"] = abs(engine["A0"]["objective"]-engine["A1"]["objective"])
    return checks


def replay_bundle(bundle):
    check_seal(bundle, "evidence_sha256")
    if bundle["classification"] != SCOPE or bundle["protocol_sha256"] != PROTOCOL_SHA or bundle["config_sha256"] != CONFIG_SHA:
        raise ValueError("bundle protocol/scope")
    runs = bundle["runs"]
    decoded = [replay_run(run) for run in runs]
    ids = [d["record"]["run_id"] for d in decoded]
    keys = [(d["record"]["config_id"], d["record"]["method"]) for d in decoded]
    if len(ids) != len(set(ids)) or len(keys) != len(set(keys)):
        raise ValueError("duplicate run/config-method")
    planned = {(c["id"], m) for c in registration()["configs"] for m in METHODS}
    if not set(keys) <= planned:
        raise ValueError("unregistered run")
    groups = {}
    for run, row in zip(runs, decoded):
        groups.setdefault(row["record"]["config_id"], []).append(run)
    checks = {}
    for config_id, group in groups.items():
        states = [json.loads(r["files"]["record.json"])["status"] for r in group]
        if len(group) == 5 and all(s == "success/certified" for s in states):
            checks[config_id] = replay_group(group)
    if bundle["status"] == "PASS" and (set(keys) != planned or len(checks) != len(registration()["configs"])):
        raise ValueError("incomplete pilot cannot pass")
    if bundle["pair_checks"] != checks:
        raise ValueError("stored pair checks mismatch")
    return dict(status=bundle["status"], runs=len(runs), pairs=len(checks),
        successes=sum(d["replay"] == "PASS" for d in decoded),
        failures=sum(d["replay"] != "PASS" for d in decoded),
        max_pair_difference=max((c["paired_objective_difference"] for c in checks.values()), default=None))


def load_bundle(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))
