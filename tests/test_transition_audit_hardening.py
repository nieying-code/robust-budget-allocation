"""Engineering-only fixtures and read-only historical replay; no solver calls."""

from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET

import pytest

from robust_budget_allocation.io import atomic
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.replay import load_bundle, replay_run
from robust_budget_allocation.pilot.restart import replay_restart
from robust_budget_allocation.pilot.storage import seal
from robust_budget_allocation.reproducibility.test_evidence import verify_junit_suites


def reseal(value, key="sha256"):
    return seal({k: v for k, v in value.items() if k != key}, key)


def junit_fixture(tests=2, skipped=0, failures=0, errors=0, returncode=0):
    cases = []
    for index in range(max(0, tests)):
        status = ("failure" if index < failures else "error" if index < failures+errors
                  else "skipped" if index < failures+errors+skipped else None)
        outcome = f"<{status}/>" if status else ""
        cases.append(f'<testcase name="engineering_{index}">{outcome}</testcase>')
    raw = (f'<testsuites><testsuite tests="{tests}" skipped="{skipped}" '
           f'failures="{failures}" errors="{errors}">{"".join(cases)}</testsuite></testsuites>').encode()
    row = dict(tests=tests, skipped=skipped, failures=failures, errors=errors,
               returncode=returncode, xml_sha256=hashlib.sha256(raw).hexdigest())
    return {"engineering": row}, {"engineering": raw}


def test_original_junit_bytes_and_utf8_archive_pass():
    suites, xml = junit_fixture()
    assert verify_junit_suites(suites, xml)
    assert verify_junit_suites(suites, {k: v.decode() for k, v in xml.items()})


@pytest.mark.parametrize("fault", ["xml", "xml_and_hash", "counter", "missing", "malformed"])
def test_junit_forgery_rejected(fault):
    suites, xml = junit_fixture()
    row = suites["engineering"]
    if fault in ("xml", "xml_and_hash"):
        xml["engineering"] = xml["engineering"].replace(b'tests="2"', b'tests="3"')
        if fault == "xml_and_hash":
            row["xml_sha256"] = hashlib.sha256(xml["engineering"]).hexdigest()
    elif fault == "counter":
        row["tests"] += 1
    elif fault == "missing":
        xml.clear()
    else:
        xml["engineering"] = b"not xml"
        row["xml_sha256"] = hashlib.sha256(xml["engineering"]).hexdigest()
    with pytest.raises(ValueError):
        verify_junit_suites(suites, xml)


@pytest.mark.parametrize("fields", [dict(tests=0), dict(tests=2, skipped=2),
    dict(skipped=1), dict(failures=1), dict(errors=1), dict(returncode=1), dict(tests=-1)])
def test_empty_failed_skipped_or_invalid_execution_rejected(fields):
    with pytest.raises(ValueError):
        verify_junit_suites(*junit_fixture(**fields))


def test_no_suites_cannot_pass():
    with pytest.raises(ValueError):
        verify_junit_suites({}, {})


@pytest.mark.parametrize("fault", ["remove_cases", "failure", "error", "skipped", "unnamed",
    "orphan_outcome", "hidden_case", "multiple_outcomes", "suite_counts", "wrapper_counts"])
def test_actual_testcases_must_match_all_summaries(fault):
    suites, xml = junit_fixture()
    root = ET.fromstring(xml["engineering"])
    suite = root.find("testsuite")
    case = suite.find("testcase")
    if fault == "remove_cases":
        for child in list(suite):
            suite.remove(child)
    elif fault in ("failure", "error", "skipped"):
        ET.SubElement(case, fault)
    elif fault == "unnamed":
        case.attrib.pop("name")
    elif fault == "orphan_outcome":
        ET.SubElement(suite, "failure")
    elif fault == "hidden_case":
        ET.SubElement(ET.SubElement(suite, "properties"), "testcase", name="hidden")
    elif fault == "multiple_outcomes":
        ET.SubElement(case, "failure")
        ET.SubElement(case, "skipped")
    elif fault == "suite_counts":
        suite.set("tests", "3")
    else:
        root.set("tests", "3")
    xml["engineering"] = ET.tostring(root)
    suites["engineering"]["xml_sha256"] = hashlib.sha256(xml["engineering"]).hexdigest()
    with pytest.raises(ValueError, match="invalid gate XML"):
        verify_junit_suites(suites, xml)


def test_nested_suites_count_cases_once_and_validate_parent_totals():
    suites, xml = junit_fixture()
    root = ET.fromstring(xml["engineering"])
    child = root.find("testsuite")
    root.remove(child)
    parent = ET.SubElement(root, "testsuite", tests="2", failures="0", errors="0", skipped="0")
    parent.append(child)
    xml["engineering"] = ET.tostring(root)
    suites["engineering"]["xml_sha256"] = hashlib.sha256(xml["engineering"]).hexdigest()
    assert verify_junit_suites(suites, xml)


def test_actual_skips_require_explicit_policy_and_some_executed_tests():
    assert verify_junit_suites(*junit_fixture(skipped=1), allow_skips=True)
    with pytest.raises(ValueError):
        verify_junit_suites(*junit_fixture(tests=1, skipped=1), allow_skips=True)


@pytest.fixture(scope="module")
def historical():
    return load_bundle(ROOT / "docs/evidence/N6_PILOT02_EVIDENCE.json.gz")


def with_original_xml(bundle):
    result = deepcopy(bundle)
    proof = load_bundle(ROOT / "docs/evidence/N6_PILOT02_PRELAUNCH.json.gz")
    result["gate_xml_files"] = {n: proof["gate_files"][n+".xml"] for n in result["gates"]["suites"]}
    return result


def test_production_replay_reads_separate_historical_and_embedded_xml(historical):
    assert replay_restart(historical)["runs"] == 80
    assert replay_restart(reseal(with_original_xml(historical), "evidence_sha256"))["runs"] == 80


@pytest.mark.parametrize("fault", ["xml", "xml_and_hash", "counter", "empty", "missing"])
def test_production_replay_rejects_resealed_test_evidence(historical, fault):
    changed = with_original_xml(historical)
    name = "solver-free"
    row = changed["gates"]["suites"][name]
    if fault in ("xml", "xml_and_hash"):
        changed["gate_xml_files"][name] = changed["gate_xml_files"][name].replace('tests="602"', 'tests="603"')
        if fault == "xml_and_hash":
            row["xml_sha256"] = hashlib.sha256(changed["gate_xml_files"][name].encode()).hexdigest()
    elif fault == "counter":
        row["tests"] += 1
    elif fault == "empty":
        row["tests"] = 0
    else:
        changed["gate_xml_files"].pop(name)
    changed["gates"] = reseal(changed["gates"])
    with pytest.raises(ValueError):
        replay_restart(reseal(changed, "evidence_sha256"))


@pytest.mark.parametrize("fault", ["remove_cases", "failure", "error", "skipped"])
def test_production_replay_rejects_actual_case_forgery_after_all_reseals(historical, fault):
    changed = with_original_xml(historical)
    name = "solver-free"
    root = ET.fromstring(changed["gate_xml_files"][name])
    if fault == "remove_cases":
        for parent in root.iter():
            for child in list(parent):
                if child.tag == "testcase":
                    parent.remove(child)
    else:
        ET.SubElement(next(root.iter("testcase")), fault)
    # Deliberately keep all declared/saved success counters unchanged.
    raw = ET.tostring(root, encoding="unicode")
    changed["gate_xml_files"][name] = raw
    changed["gates"]["suites"][name]["xml_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    changed["gates"] = reseal(changed["gates"])
    changed["roundtrip"]["gate_sha256"] = changed["gates"]["sha256"]
    changed["roundtrip"] = reseal(changed["roundtrip"])
    with pytest.raises(ValueError, match="invalid gate XML"):
        replay_restart(reseal(changed, "evidence_sha256"))


def replace_result(saved, result):
    saved["files"]["result.json"] = json.dumps(reseal(result, "result_sha256"))
    for row in saved["manifest"]["files"]:
        raw = saved["files"][row["path"]].encode()
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    saved["manifest"] = reseal(saved["manifest"])


@pytest.mark.parametrize("field", ["packages", "python", "extra"])
def test_engine_other_source_content_rejected_despite_matching_git_and_reseals(historical, field):
    saved = deepcopy(next(r for r in historical["runs"] if json.loads(r["files"]["record.json"])["method"] == "EF"))
    result = json.loads(saved["files"]["result.json"])
    engine = result["engine"]
    source = engine["audit"]["source"]
    original_git = deepcopy(source["git"])
    if field == "packages":
        source["packages"]["Pyomo"] = "forged"
    elif field == "python":
        source["python"]["executable"] += "-forged"
    else:
        source["extra"] = {"untrusted": True}
    engine["audit"]["source"] = reseal(source, "manifest_sha256")
    assert source["git"] == original_git
    result["engine"] = reseal(engine, "result_sha256")
    replace_result(saved, result)
    with pytest.raises(ValueError, match="engine complete source binding"):
        replay_run(saved)


def test_engine_canonical_tuple_list_equivalence(historical):
    saved = deepcopy(next(r for r in historical["runs"] if json.loads(r["files"]["record.json"])["method"] == "EF"))
    result = json.loads(saved["files"]["result.json"])
    source = result["engine"]["audit"]["source"]
    source["git"]["untracked_paths"] = tuple(source["git"]["untracked_paths"])
    replace_result(saved, result)
    assert replay_run(saved)["replay"] == "PASS"


@pytest.mark.parametrize("method", ["EF", "A0", "A1"])
@pytest.mark.parametrize("fault", ["seal", "audit", "both", "audit_none", "audit_empty",
    "source", "environment", "data", "data_sha256", "config", "config_sha256",
    "classification", "scenario_order", "scenario_sha256", "protocol_path", "protocol_sha256"])
def test_required_method_audit_cannot_be_deleted_in_run_or_batch(historical, method, fault):
    changed = deepcopy(historical)
    saved = next(r for r in changed["runs"] if json.loads(r["files"]["record.json"])["method"] == method)
    result = json.loads(saved["files"]["result.json"])
    engine = result["engine"]
    original_git = deepcopy(engine["audit"]["source"]["git"])
    engine["audit"]["source"]["packages"]["Pyomo"] = "forged"
    engine["audit"]["source"] = reseal(engine["audit"]["source"], "manifest_sha256")
    assert engine["audit"]["source"]["git"] == original_git
    if fault in ("seal", "both"):
        engine.pop("result_sha256")
    if fault in ("audit", "both"):
        engine.pop("audit")
    elif fault == "audit_none":
        engine["audit"] = None
    elif fault == "audit_empty":
        engine["audit"] = {}
    elif fault != "seal":
        engine["audit"].pop(fault)
    if "result_sha256" in engine:
        result["engine"] = reseal(engine, "result_sha256")
    replace_result(saved, result)  # Recompute outer result and complete file inventory.
    with pytest.raises(ValueError, match="required engine audit fields"):
        replay_run(saved)
    with pytest.raises(ValueError, match="required engine audit fields"):
        replay_restart(reseal(changed, "evidence_sha256"))


@pytest.mark.parametrize("field", ["a1_protocol_path", "a1_protocol_sha256"])
def test_a1_protocol_audit_fields_mandatory(historical, field):
    changed = deepcopy(historical)
    saved = next(r for r in changed["runs"] if json.loads(r["files"]["record.json"])["method"] == "A1")
    result = json.loads(saved["files"]["result.json"])
    result["engine"]["audit"].pop(field)
    result["engine"] = reseal(result["engine"], "result_sha256")
    replace_result(saved, result)
    with pytest.raises(ValueError, match="required engine audit fields"):
        replay_run(saved)
    with pytest.raises(ValueError, match="required engine audit fields"):
        replay_restart(reseal(changed, "evidence_sha256"))


@pytest.mark.parametrize("method", ["M0", "M1"])
def test_original_ablation_format_stays_valid(historical, method):
    saved = next(r for r in historical["runs"] if json.loads(r["files"]["record.json"])["method"] == method)
    engine = json.loads(saved["files"]["result.json"])["engine"]
    assert "audit" not in engine and "result_sha256" not in engine
    assert replay_run(saved)["replay"] == "PASS"


@pytest.fixture
def archive_writer():
    spec = importlib.util.spec_from_file_location("archive_entry", ROOT / "scripts/n6_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # main/worker are NOT called.
    return module.archive


@pytest.mark.parametrize("failures", [0, 2, atomic.ATOMIC_REPLACE_MAX_ATTEMPTS])
def test_archive_uses_existing_bounded_retry(tmp_path, monkeypatch, archive_writer, failures):
    real_replace = atomic.os.replace
    attempts, waits = [], []
    def conflicting_replace(source, target):
        attempts.append(1)
        if len(attempts) <= failures:
            raise PermissionError("synthetic transient sharing conflict")
        real_replace(source, target)
    monkeypatch.setattr(atomic.os, "replace", conflicting_replace)
    monkeypatch.setattr(atomic, "sleep", waits.append)
    path = tmp_path / "engineering.json.gz"
    if failures == atomic.ATOMIC_REPLACE_MAX_ATTEMPTS:
        with pytest.raises(PermissionError):
            archive_writer(path, {"engineering_fixture": True})
        assert not path.exists()
        assert len(attempts) == failures and len(waits) == failures-1
    else:
        archive_writer(path, {"engineering_fixture": True})
        assert json.loads(gzip.decompress(path.read_bytes())) == {"engineering_fixture": True}
        assert len(attempts) == failures+1 and len(waits) == failures
    assert all(w == atomic.ATOMIC_REPLACE_RETRY_SECONDS for w in waits)
    assert not list(tmp_path.glob(".n6-*"))


def test_archive_deterministic_and_no_overwrite(tmp_path, archive_writer):
    first, second = tmp_path / "a.gz", tmp_path / "b.gz"
    archive_writer(first, {"b": 2, "a": 1})
    archive_writer(second, {"a": 1, "b": 2})
    original = first.read_bytes()
    assert original == second.read_bytes()
    with pytest.raises(FileExistsError):
        archive_writer(first, {"changed": True})
    assert first.read_bytes() == original
