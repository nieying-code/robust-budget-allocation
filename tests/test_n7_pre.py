"""N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS; solver-free tests."""

import base64
from copy import deepcopy
import json
import random
import subprocess

import pytest

from robust_budget_allocation.algorithms.common import tolerance
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.storage import seal
from robust_budget_allocation.pilot.replay import load_bundle
from robust_budget_allocation.mechanism_confirmation import configuration as config, audit, execution
from robust_budget_allocation.mechanism_confirmation.diagnosis import effective, memory_diagnosis, option_gate, summarize

CONFIGS = config.registration()["configs"]


def test_complete_preregistered_matrix_and_seed_partition():
    assert len(CONFIGS) == 54 and len({c["id"] for c in CONFIGS}) == 54
    assert len({c["seed"] for c in CONFIGS}) == 6
    assert not {61001, 61002} & {c["seed"] for c in CONFIGS}
    assert all(c["regime"] == "F" and c["layer"] == 1 for c in CONFIGS[:18])
    assert all(c["layer"] == 2 for c in CONFIGS[18:])
    assert {c["risk"] for c in CONFIGS} == {.4} and {c["scenarios"] for c in CONFIGS} == {12}
    for regime in ("F", "R", "B"):
        for budget in (45, 90, 150):
            assert len([c for c in CONFIGS if c["regime"] == regime and c["budget"] == budget]) == 6


@pytest.mark.parametrize("item", CONFIGS, ids=lambda c:c["id"])
def test_all_54_inputs_obey_frozen_domains_and_economics(item):
    data = config.generate(item)
    data.validate()
    assert data.option_cap == 45 and data.option_fee == item["option_fee"]
    assert data.base.shortage_penalty == 8 and len(data.base.scenarios) == 12
    assert config.generate(item).to_dict() == data.to_dict()
    assert all(max(data.base.unit_cost.values()) < p < 8 for p in data.emergency_price.values())
    for j, fixed, unit in zip(data.base.suppliers, (2, 2.5, 3), (.18, .22, .25)):
        assert data.reliability.fixed_premium[j]["1"] == fixed*item["premium_multiplier"]
        assert data.reliability.unit_premium[j]["1"] == unit*item["premium_multiplier"]


def test_common_variates_and_unchanged_generation_structure():
    for seed in {c["seed"] for c in CONFIGS}:
        paired = [config.generate(c) for c in CONFIGS if c["seed"] == seed]
        for data in paired:
            assert data.base.demand == paired[0].base.demand
            assert data.reliability.fulfillment == paired[0].reliability.fulfillment
        rng = random.Random(seed)
        demand = round(60+40*rng.random(), 8)
        assert paired[0].base.demand["w000"] == demand
        for j in ("j0", "j1", "j2"):
            state, severity = rng.random(), rng.random()
            rho = round(.10+.30*severity if state < .4 else .85+.15*severity, 8)
            assert paired[0].base.base_fulfillment["w000"][j] == rho
        v = rng.random()
        for c in [c for c in CONFIGS if c["seed"] == seed]:
            assert config.generate(c).emergency_price["w000"] == round(c["price_intercept"]+c["price_slope"]*v, 8)


@pytest.mark.parametrize("field,value", [("seed", 61001), ("budget", 100), ("scenarios",24),
    ("risk",.8), ("option_fee",0), ("premium_multiplier",2), ("price_intercept",1)])
def test_unregistered_parameter_changes_rejected(field, value):
    changed = {**CONFIGS[0], field:value}
    with pytest.raises(ValueError, match="unregistered"): config.generate(changed)


@pytest.mark.parametrize("purchase,g,e,delta,expected", [
    (1,1,2,1,True), (0,1,2,1,False), (1,0,2,1,False), (1,1,0,1,False),
    (1,1e-12,1e-12,1,False), (1,1,2,1e-8,False), (1,1,2,-1,False),
])
def test_effective_option_three_conditions(purchase,g,e,delta,expected):
    result=effective(100+delta,100,dict(y_F=purchase,scenarios=[dict(scenario="w",g=g,E=e)]))
    assert result["EFFECTIVE_OPTION_ACTIVE"] == expected
    assert result["numerical_tolerance"] == tolerance(100+delta,100)


def gate_rows(counts):
    return [dict(config=c, option=dict(EFFECTIVE_OPTION_ACTIVE=c["seed_index"] <= counts.get(c["budget"],0)))
            for c in CONFIGS[:18]]


@pytest.mark.parametrize("counts,status", [({},"FAILED"),({45:2,90:2,150:2},"INCONCLUSIVE"),
    ({90:3},"PASSED"),({45:6},"PASSED")])
def test_gate_is_cell_based_not_pooled_or_budget_only(counts,status):
    assert option_gate(gate_rows(counts))["status"] == "N7_PRE_OPTION_GATE_"+status


def test_gate_requires_all18_ordered_configs_even_if_three_successes_already():
    rows = gate_rows({45:6})
    for bad in (rows[:6], rows[:-1], rows[::-1], rows+[rows[0]]):
        with pytest.raises(ValueError): option_gate(bad)


def toy_memory(eligible=True, nonterminal=True, active=True, hit=False):
    entry=dict(scenario="w", last_iteration=1)
    row1=dict(iteration=1,memory_before=[],memory_after=[entry],phase_i=dict(ranking=[],evaluations=[],hit=False),
        phase_ii=None,phase_iii=None,first_stage=dict(y_F=0),certified=False,added_scenario="a")
    row2=dict(iteration=2,memory_before=[entry],memory_after=[entry],
        phase_i=dict(ranking=[entry] if eligible else [],planned=["w"] if eligible else [],
                     evaluations=[dict(g=1,E=2)] if eligible else [],hit=hit),
        phase_ii=None,phase_iii=None,first_stage=dict(y_F=int(active)),
        certified=not nonterminal,added_scenario="b" if nonterminal else None)
    return dict(trace=[row1,row2],phase_i_hits=int(hit))


def test_memory_population_terminal_and_active_only_are_not_opportunities():
    a1=toy_memory()
    assert memory_diagnosis(a1)["opportunities"] == 1
    assert memory_diagnosis(toy_memory(nonterminal=False))["opportunities"] == 0
    assert memory_diagnosis(toy_memory(nonterminal=False))["eligible_terminal_iterations"] == 1
    assert memory_diagnosis(toy_memory(eligible=False))["opportunities"] == 0
    one=toy_memory(); one["trace"]=one["trace"][:1]
    assert memory_diagnosis(one)["opportunities"] == 0


@pytest.mark.parametrize("eligible,active,hit,status", [
    (True,True,False,"MEMORY_REMOVAL_REQUIRES_NEW_CORRECTNESS"),
    (True,True,True,"N7_PRE_MEMORY_REVIEW_REQUIRED"),
    (False,True,False,"N7_PRE_MEMORY_NOT_IDENTIFIED"),
    (True,False,False,"N7_PRE_MEMORY_NOT_IDENTIFIED"),
])
def test_memory_decision_is_relevant_opportunity_based(eligible,active,hit,status):
    workload=dict.fromkeys(("phase_i_hits","phase_ii_hits","phase_iii_calls","exact_oracle_calls",
        "complete_oracle_calls","scenario_evaluations","iterations","scenarios_added"),0)
    row=dict(config=CONFIGS[0],option=dict(EFFECTIVE_OPTION_ACTIVE=False),
        memory=memory_diagnosis(toy_memory(eligible=eligible,active=active,hit=hit)),workload={"A0":workload,"A1":workload})
    assert summarize([row])["memory_decision"] == status


@pytest.fixture
def real_source(tmp_path, monkeypatch):
    root = tmp_path / "source"; root.mkdir()
    for name in audit.FIXED:
        target = root / name; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((config.ROOT/name).read_bytes())
    code=root/"src/robust_budget_allocation/example.py";code.parent.mkdir(parents=True,exist_ok=True);code.write_text("# source fixture\n")
    def git(*args):
        return subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True)
    git("init");git("config","user.name","test");git("config","user.email","test@example.invalid")
    git("config","core.autocrlf","false");git("add",".");git("commit","-m","fixture")
    monkeypatch.setattr(audit,"ROOT",root)
    source=audit.source();objects=audit.proof(source)
    return root, source, objects


def test_real_source_proof_and_json_roundtrip(real_source):
    root, source, objects=real_source
    audit.verify_source(json.loads(json.dumps(source)),json.loads(json.dumps(objects)))
    assert audit.same(source,json.loads(json.dumps(source)))
    raw=deepcopy(source);raw["git"]["untracked_paths"]=tuple(raw["git"]["untracked_paths"])
    assert audit.same(raw,source)
    bad=deepcopy(objects);oid=source["git"]["commit_sha"];bad[oid]["base64"]=base64.b64encode(b"fake").decode()
    with pytest.raises(ValueError,match="object hash"):audit.verify_source(source,bad)
    path=root/"bundle.gz";audit.save_archive(path,dict(source=source,git_objects=objects))
    assert audit.load_archive(path)["source"]==source
    with pytest.raises(FileExistsError):audit.save_archive(path,{})


def test_production_gate_validator_roundtrip_and_real_source_change(real_source,tmp_path,monkeypatch):
    root, source, objects=real_source
    directory=tmp_path/"gates";directory.mkdir()
    suites={}
    for name in ("solver-free","licensed"):
        xml=directory/(name+".xml");xml.write_text('<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"/></testsuites>')
        suites[name]=dict(tests=1,failures=0,errors=0,skipped=0,returncode=0,xml_sha256=sha256_file(xml))
    gate_example=load_bundle(config.ROOT/"docs/evidence/N6_PILOT02_EVIDENCE.json.gz")["gates"]["environment"]
    payload=dict(status="PASS",source=source,git_objects=objects,environment=gate_example,
        frozen_hashes=config.FROZEN,suites=suites,
        xml_files={n:(directory/(n+".xml")).read_bytes().decode("utf-8") for n in suites})
    monkeypatch.setattr(execution,"GATES",directory)
    atomic_write_json(directory/"gates.json",seal(payload))
    assert execution.validate_gates()["source"] == source
    for kind in ("missing_object", "xml", "count", "license_skipped"):
        bad=deepcopy(payload)
        if kind == "missing_object": bad["git_objects"].pop(source["git"]["commit_sha"])
        if kind == "xml": bad["xml_files"]["licensed"] += "tamper"
        if kind == "count": bad["suites"]["licensed"]["tests"] += 1
        if kind == "license_skipped": bad["suites"]["licensed"]["skipped"] += 1
        with pytest.raises(ValueError): audit.verify_gate(seal(bad),source)
    payload["source"]=deepcopy(source);payload["source"]["packages"]["Pyomo"]="forged"
    payload["source"].pop("manifest_sha256");payload["source"]=seal(payload["source"],"manifest_sha256")
    atomic_write_json(directory/"gates.json",seal(payload))
    with pytest.raises(ValueError,match="prelaunch source"): execution.validate_gates()
