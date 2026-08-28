"""Serialization integration: real Git/N1 manifests, JSON, inventory and replay.

Only solver execution/mathematical optimality are simulated. No source validator,
run reader, group/bundle/restart replay, or canonical comparison is mocked.
All simulated gates/results live in pytest temporary directories, not pilot output.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from robust_budget_allocation.algorithms.common import settings
from robust_budget_allocation.io.atomic import atomic_write_json, atomic_write_text
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.pilot import restart as r, replay, source_archive
from robust_budget_allocation.pilot.configuration import (
    ROOT, registration, execution_order, generate, binding, SCOPE, PROTOCOL_SHA, CONFIG_SHA)
from robust_budget_allocation.pilot.storage import seal, file_manifest, read_run


def reseal(value, key):
    return seal({k: v for k, v in value.items() if k != key}, key)


def alter(source, kind):
    if kind == "input":
        source["inputs"][0]["sha256"] = "0"*64
    elif kind == "tree":
        source["git"]["tree_sha"] = "0"*40
    elif kind == "commit":
        source["git"]["commit_sha"] = "0"*40
    elif kind == "package":
        source["packages"]["Pyomo"] = "changed"
    elif kind == "python":
        source["python"]["executable"] += "-changed"
    elif kind == "extra":
        source["unexpected_field"] = {"nested": "must not be ignored"}
    else:
        raise AssertionError(kind)
    return source


@pytest.fixture
def chain(tmp_path, monkeypatch):
    root = tmp_path / "source-repo"
    root.mkdir()
    # Real, newly created source tree, not an old execution gate promoted to approval.
    paths = []
    for name in sorted(source_archive.FIXED | {"src/robust_budget_allocation/fixture.py"}):
        path = root / name
        atomic_write_text(path, "temporary serialization fixture: "+name+"\n")
        paths.append(path)
    atomic_write_text(root / ".gitignore", "outputs/\n")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT)
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=Serialization Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "temporary source fixture")
    monkeypatch.setattr(r, "ROOT", root)
    monkeypatch.setattr(source_archive, "ROOT", root)
    monkeypatch.setattr(r, "source_inputs", lambda: paths)
    # Route the real N1 validator to the isolated repo; do NOT replace it with success.
    monkeypatch.setattr(r, "source_gate", lambda: validate_source_state(
        root, required_tracked_paths=paths, scientific_roots=("src", "scripts", "configs")))
    gates = root / "outputs/serialization-test-gates"
    monkeypatch.setattr(r, "GATES", gates)
    monkeypatch.setattr(r, "GATE_FILE", gates / "gates.json")
    source = r.manifest()
    assert type(source["git"]["untracked_paths"]) is tuple
    environment = dict(python="3.12.10", python_implementation="CPython", pyomo="6.10.1",
        gurobipy="13.0.2", gurobi_optimizer="13.0.2", solver_interface="gurobi_direct",
        threads=1, solver_available=True, license_available=True, status="PASS",
        platform="SIMULATED TEST ENVIRONMENT; NOT A LICENSE CHECK")
    suites = {}
    for name in ("solver-free", "licensed", "windows-stress"):
        xml = gates / (name+".xml")
        atomic_write_text(xml, '<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
        suites[name] = dict(tests=1, failures=0, errors=0, skipped=0, returncode=0,
                           xml_sha256=sha256_file(xml))
    gate = seal(dict(status="PASS", batch_id=r.BATCH, source=source, environment=environment,
        suites=suites, protocol_sha256=PROTOCOL_SHA, config_sha256=CONFIG_SHA,
        purpose="SIMULATED SERIALIZATION FIXTURE ONLY"))
    atomic_write_json(r.GATE_FILE, gate)
    saved_gate = json.loads(r.GATE_FILE.read_text(encoding="utf-8"))
    assert saved_gate["source"] != source
    r.validate_gates(saved_gate)  # REAL source comparison + seals + Git-object + XML checks

    # Only the scientific solve/optimality proof is simulated, explicitly labelled.
    def simulated_proof(data, engine):
        assert engine["simulation"] is True
        return True
    def simulated_three(data, ef, a0, a1):
        assert all(e["simulation"] is True for e in (ef, a0, a1))
        return {"simulated_optimality_only": True}
    monkeypatch.setattr(replay, "verify_engine", simulated_proof)
    monkeypatch.setattr(replay, "verify_three", simulated_three)

    class Chain:
        calls = 0
        fail_at = None
        tamper = None
        captured = None

        def run(self, output_root, run_id, config, method):
            index = self.calls
            self.calls += 1
            data = generate(config)
            source = r.manifest()
            folder = output_root / run_id
            folder.mkdir()
            shared = dict(run_id=run_id, parent_run_id=None, parent_batch_id=None,
                retry_reason=None, lineage=None, purpose="pilot", method=method,
                source=source, binding=binding(config, data))
            request = dict(**shared, config=config, solver_config=settings())
            atomic_write_json(folder / "request.json", request)
            # Always validate the request; corruption is injected only afterwards.
            r.validate_worker(folder, json.loads((folder / "request.json").read_text(encoding="utf-8")))
            if self.tamper is not None:
                source = reseal(alter(source, self.tamper), "manifest_sha256")
                shared["source"] = source
            decision = dict(q_by_level={j: {k: 0. for k in data.reliability.levels[j]}
                                        for j in data.base.suppliers},
                            reliability_choice={j: "0" for j in data.base.suppliers}, y_F=0)
            engine = seal(dict(simulation=True, method=method, objective=999., runtime_seconds=0.,
                solver=dict(lower_bound=999., runtime_seconds=0.), first_stage=decision,
                incumbent=dict(first_stage=decision), trace=[],
                audit=dict(source=source, data=data.to_dict(), data_sha256=data.data_sha256,
                           config=settings(), config_sha256=canonical_json_sha256(settings()),
                           environment=environment)), "result_sha256")
            status = "incomplete" if index == self.fail_at else "success/certified"
            result = seal(dict(run_id=run_id, status=status, engine=engine,
                solver_config=settings(), max_iterations=len(data.base.scenarios)+1,
                metrics=replay.metrics(engine), mechanism=replay.mechanism(data, engine),
                timing={}, environment=environment), "result_sha256")
            record = seal(dict(**shared, classification=SCOPE, config_id=config["id"],
                status=status, certified=status == "success/certified", metrics=result["metrics"],
                trace_sha256=canonical_json_sha256([]), environment=environment,
                watchdog=dict(status=None, exit_code=0, cleanup=dict(success=True, exit_code=0))),
                "output_sha256")
            atomic_write_json(folder / "result.json", result)
            atomic_write_json(folder / "record.json", record)
            atomic_write_json(folder / "heartbeat.json", dict(run_id=run_id, stage="complete"))
            for name in ("stdout.txt", "stderr.txt"):
                atomic_write_text(folder / name, "SIMULATED SOLVE; NO SCIENTIFIC RUN\n")
            file_manifest(folder)
            return folder

        def archive(self, path, payload):
            # Exercise both final in-memory replay and the archive JSON round trip.
            atomic_write_json(path.with_suffix(".json"), payload)
            self.captured = payload
            self.loaded = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))

        def execute(self):
            return r.execute(r.BATCH, self.archive)

    fixture = Chain()
    monkeypatch.setattr(r, "run_one", fixture.run)
    fixture.root, fixture.source, fixture.gate = root, source, saved_gate
    return fixture


@pytest.mark.parametrize("batch", [None, "n6pilot01", "n6diagnostic01", "n6pilot03", "../n6pilot02"])
def test_only_fresh_fixed_batch_authorized(batch):
    with pytest.raises(PermissionError):
        r.execute(batch, lambda *a: pytest.fail("archive not authorized"))


def test_real_json_first_result_and_final_80_replay(chain):
    assert chain.execute() == 0
    assert chain.calls == 80 and chain.captured["status"] == "PASS"
    first = chain.captured["runs"][0]
    record = json.loads(first["files"]["record.json"])
    assert record["source"] != chain.captured["source"]  # list vs tuple, actually exercised
    assert r.same_content(record["source"], chain.captured["source"])
    assert replay.replay_run(first)["replay"] == "PASS"
    for bundle in (chain.captured, chain.loaded):
        assert r.replay_restart(bundle) == dict(status="PASS", runs=80, pairs=16,
            successes=80, failures=0, max_pair_difference=0.)
    expected = [(f"n6pilot02-{i:02d}-{m.lower()}", c, m)
                for i, c in enumerate(registration()["configs"]) for m in execution_order(i)]
    actual = [(json.loads(x["files"]["record.json"])["run_id"],
               json.loads(x["files"]["request.json"])["config"],
               json.loads(x["files"]["record.json"])["method"]) for x in chain.loaded["runs"]]
    assert actual == expected
    with pytest.raises(FileExistsError):
        chain.execute()


@pytest.mark.parametrize("kind", ["input", "tree", "commit", "package", "python", "extra"])
@pytest.mark.parametrize("resealed", [False, True])
def test_gate_real_content_change_rejected_even_with_digest_reused_or_resealed(chain, kind, resealed):
    gate = deepcopy(chain.gate)
    original_digest = gate["source"]["manifest_sha256"]
    alter(gate["source"], kind)
    if resealed:
        gate["source"] = reseal(gate["source"], "manifest_sha256")
    else:
        assert gate["source"]["manifest_sha256"] == original_digest
    gate = reseal(gate, "sha256")
    with pytest.raises(ValueError, match="gate/source"):
        r.validate_gates(gate)


@pytest.mark.parametrize("kind", ["input", "tree", "commit", "package", "python", "extra"])
def test_first_loaded_result_source_mutation_stops_before_next_run(chain, kind):
    chain.tamper = kind
    assert chain.execute() == 1
    assert chain.calls == 1
    assert chain.captured["failure"]["exception"]["message"] == "mixed batch source"


def test_real_tracked_file_change_invalidates_gate(chain):
    atomic_write_text(chain.root / "src/robust_budget_allocation/fixture.py", "changed source\n")
    with pytest.raises(ValueError, match="gate/source"):
        r.validate_gates(chain.gate)
    with pytest.raises(RuntimeError, match="staged or unstaged"):
        r.source_gate()


def test_non_success_stops_and_retains_first_record(chain):
    chain.fail_at = 0
    assert chain.execute() == 1 and chain.calls == 1
    assert chain.captured["failure"]["status"] == "incomplete"


@pytest.mark.parametrize("where", ["bundle", "claim", "gate"])
def test_final_memory_replay_rejects_real_source_change(chain, where):
    # One failed simulated run suffices to test source binding in final replay.
    chain.fail_at = 0
    assert chain.execute() == 1
    forged = deepcopy(chain.captured)
    target = {"bundle": forged, "claim": forged["batch_start"], "gate": forged["gates"]}[where]
    target["source"] = reseal(alter(deepcopy(target["source"]), "package"), "manifest_sha256")
    if where != "bundle":
        forged["batch_start" if where == "claim" else "gates"] = reseal(target, "sha256")
    forged = reseal(forged, "evidence_sha256")
    with pytest.raises(ValueError, match="source"):
        r.replay_restart(forged)


def test_worker_claim_comparison_preserves_all_source_fields(chain):
    chain.fail_at = 0
    assert chain.execute() == 1
    folder = chain.root / "outputs/pilot/n6pilot02/n6pilot02-00-m0"
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    r.validate_worker(folder, request)
    request["source"] = reseal(alter(request["source"], "extra"), "manifest_sha256")
    with pytest.raises(ValueError, match="unique batch source"):
        r.validate_worker(folder, request)


def test_canonical_comparison_rejects_nonfinite_and_preserves_array_order():
    assert r.same_content({"a": (1, 2), "b": 3}, {"b": 3, "a": [1, 2]})
    assert not r.same_content({"a": [1, 2]}, {"a": [2, 1]})
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            r.same_content({"x": value}, {"x": value})


@pytest.mark.parametrize("action", ["run", "worker", "restart-gates", "diagnostic-retry"])
def test_cli_interlock_blocks_all_execution_actions(action):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/n6_pilot.py"), action],
                            capture_output=True, text=True)
    assert result.returncode != 0 and "N6_PILOT_RELAUNCH_NOT_AUTHORIZED" in result.stderr
