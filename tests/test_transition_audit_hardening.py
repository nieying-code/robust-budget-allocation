"""Engineering-only fixtures and read-only historical replay; no solver calls."""

from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json

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
    raw = (f'<testsuites><testsuite tests="{tests}" skipped="{skipped}" '
           f'failures="{failures}" errors="{errors}"/></testsuites>').encode()
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
