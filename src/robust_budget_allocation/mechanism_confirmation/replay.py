"""Solver-free N7-pre replay using embedded source objects, not live history."""

import json

from robust_budget_allocation.algorithms.common import settings, upper
from robust_budget_allocation.algorithms.a1_verification import verify_three
from robust_budget_allocation.io.hashing import canonical_json_sha256
from robust_budget_allocation.pilot.measurement import verify_engine, metrics, mechanism
from robust_budget_allocation.pilot.replay import verify_environment
from robust_budget_allocation.pilot.storage import check_seal, verify_inventory
from .configuration import SCOPE, FROZEN, METHODS, generate, binding, registration, order
from .audit import same, verify_source, verify_gate
from .diagnosis import observation, summarize


def replay_run(saved, source):
    verify_inventory(saved["manifest"], saved["files"])
    request, record, result = [json.loads(saved["files"][n+".json"]) for n in ("request", "record", "result")]
    check_seal(request)
    check_seal(record, "output_sha256")
    check_seal(result, "result_sha256")
    if record["classification"] != SCOPE or request["classification"] != SCOPE:
        raise ValueError("wrong study scope")
    for key in ("run_id", "method", "config", "binding", "source", "batch_id"):
        if not same(request[key], record[key]):
            raise ValueError("request/record " + key)
    if not same(record["source"], source) or record["method"] not in METHODS:
        raise ValueError("mixed source or method")
    if record["retry_reason"] is not None or record["parent_run_id"] is not None:
        raise ValueError("unregistered retry")
    data = generate(record["config"])
    if record["binding"] != binding(record["config"], data) or request["solver_config"] != settings():
        raise ValueError("registered data/settings binding")
    if record["certified"] != (record["status"] == "success/certified"):
        raise ValueError("false certification")
    if record["status"] != "success/certified":
        return dict(record=record, result=result, replay="FAILURE_RETAINED")
    heartbeat = json.loads(saved["files"]["heartbeat.json"])
    watch = record["watchdog"]
    if (result["status"] != record["status"] or result["run_id"] != record["run_id"]
        or heartbeat["stage"] != "complete" or heartbeat["run_id"] != record["run_id"]
        or watch["status"] is not None or watch["exit_code"] != 0 or not watch["cleanup"]["success"]):
        raise ValueError("incomplete supervised run")
    verify_environment(result["environment"])
    if record["environment"] != result["environment"] or result["solver_config"] != settings():
        raise ValueError("environment/solver binding")
    engine = result["engine"]
    if engine["method"] != record["method"] or result["classification"] != SCOPE:
        raise ValueError("worker method/scope")
    if "audit" in engine:
        check_seal(engine, "result_sha256")
        audit = engine["audit"]
        if not same(audit["source"], source) or audit["data"] != data.to_dict() or audit["data_sha256"] != data.data_sha256:
            raise ValueError("engine source/data binding")
        verify_environment(audit["environment"])
        if audit["config_sha256"] != canonical_json_sha256(audit["config"]):
            raise ValueError("engine config hash")
        if any(audit["config"][k] != v for k, v in settings().items()):
            raise ValueError("engine solver settings")
    verify_engine(data, engine)
    if record["trace_sha256"] != canonical_json_sha256(engine.get("trace", [])):
        raise ValueError("trace hash")
    if record["metrics"] != metrics(engine) or result["metrics"] != record["metrics"] or result["mechanism"] != mechanism(data, engine):
        raise ValueError("derived metrics/accounting")
    return dict(record=record, result=result, replay="PASS")


def replay_group(group, source):
    decoded = [replay_run(r, source) for r in group]
    if len(decoded) != 5 or any(r["replay"] != "PASS" for r in decoded):
        raise ValueError("incomplete config")
    config = decoded[0]["record"]["config"]
    if any(r["record"]["config"] != config for r in decoded):
        raise ValueError("unpaired config")
    engines = {r["record"]["method"]: r["result"]["engine"] for r in decoded}
    if set(engines) != set(METHODS):
        raise ValueError("config method inventory")
    data = generate(config)
    checks = verify_three(data, engines["EF"], engines["A0"], engines["A1"])
    upper(engines["EF"]["objective"], engines["M1"]["objective"], "M2<=M1")
    upper(engines["M1"]["objective"], engines["M0"]["objective"], "M1<=M0")
    return observation(config, data, engines, checks)


def replay_bundle(bundle):
    check_seal(bundle, "evidence_sha256")
    if bundle["classification"] != SCOPE or bundle["frozen_hashes"] != FROZEN or bundle["status"] not in ("PASS", "FAIL"):
        raise ValueError("study scope/registration")
    verify_source(bundle["source"], bundle["git_objects"])
    verify_gate(bundle["gates"], bundle["source"])
    expected = [(i, c, m) for i, c in enumerate(registration()["configs"]) for m in order(i)]
    if len(bundle["runs"]) > len(expected):
        raise ValueError("excess runs")
    observations = []
    for index, saved in enumerate(bundle["runs"]):
        row = replay_run(saved, bundle["source"])["record"]
        i, config, method = expected[index]
        if row["config"] != config or row["method"] != method or row["run_id"] != f"n7pre01-{i:02d}-{method.lower()}":
            raise ValueError("frozen execution order/identity")
        if row["batch_id"] != "n7pre01":
            raise ValueError("mixed batch")
        if index >= 90:
            prior = summarize(observations[:18])
            if prior["gate"]["status"] != "N7_PRE_OPTION_GATE_PASSED":
                raise ValueError("Layer2 without Gate M")
        if index % 5 == 4 and all(json.loads(r["files"]["record.json"])["certified"] for r in bundle["runs"][index-4:index+1]):
            observations.append(replay_group(bundle["runs"][index-4:index+1], bundle["source"]))
        if not row["certified"] and index != len(bundle["runs"])-1:
            raise ValueError("execution continued after failure")
    if not same(observations, bundle["observations"]):
        raise ValueError("stored observations not reconstructed")
    summary = summarize(observations)
    if bundle["status"] == "PASS":
        if bundle["failure"] is not None or len(observations) not in (18, 54):
            raise ValueError("incomplete diagnostic cannot pass execution")
        required = 54 if summary["gate"]["status"] == "N7_PRE_OPTION_GATE_PASSED" else 18
        if len(observations) != required or len(bundle["runs"]) != required*5:
            raise ValueError("layer stop/continuation rule")
    if not same(bundle["summary"], summary):
        raise ValueError("diagnostic summary mismatch")
    return dict(status=bundle["status"], runs=len(bundle["runs"]), completed_configs=len(observations),
                gate=summary["gate"], memory_decision=summary["memory_decision"],
                max_objective_difference=max((o["correctness"]["max_objective_difference"] for o in observations), default=None))
