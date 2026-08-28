"""Real depth=1 clones and production replay CLI; no monkeypatch or history fetch."""

import base64
import gzip
import json
import os
import subprocess
import sys

import pytest

from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.pilot.storage import seal

EXECUTION = "ec6bbfc55e333483efa41f866c0e8f26d13cd18f"
PROOF = "docs/evidence/N6_PILOT02_PRELAUNCH.json.gz"
EVIDENCE = "docs/evidence/N6_PILOT02_EVIDENCE.json.gz"


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


def assert_shallow_without_execution(folder):
    assert git(folder, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    assert git(folder, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert git(folder, "cat-file", "-e", EXECUTION+"^{commit}").returncode != 0
    assert not (folder / "outputs").exists()


@pytest.fixture
def shallow(tmp_path):
    folder = tmp_path / "depth-one"
    result = subprocess.run(["git", "clone", "--depth=1", "--no-local", "--single-branch",
                             ROOT.as_uri(), str(folder)], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stderr
    assert_shallow_without_execution(folder)
    # Tests must exercise the committed delivery, not an overlay of repaired
    # working files onto an older clone. Commit changes before running this test.
    for name in ("scripts/n6_pilot.py", "src/robust_budget_allocation/pilot/source_archive.py"):
        assert (folder / name).read_bytes() == (ROOT / name).read_bytes()
    return folder


def cli_replay(folder):
    env = dict(os.environ, PYTHONPATH=str(folder / "src"),
               GRB_LICENSE_FILE=str(folder / "nonexistent-license"))
    result = subprocess.run([sys.executable, "scripts/n6_pilot.py", "replay",
                             "--evidence", EVIDENCE], cwd=folder, env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=120)
    assert_shallow_without_execution(folder)
    return result


def test_real_shallow_clone_production_cli_replays_all_80_without_license(shallow):
    result = cli_replay(shallow)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(status="PASS", runs=80, pairs=16,
        successes=80, failures=0, max_pair_difference=0.0)
    assert not git(shallow, "status", "--porcelain").stdout.strip()


@pytest.mark.parametrize("fault,message", [
    ("missing_file", "missing Git source proof object"),
    ("missing_commit", "missing Git source proof object"),
    ("object_bytes", "Git source proof object hash"),
    ("envelope", "self hash mismatch"),
    ("tree", "source commit/tree mismatch"),
    ("inventory", "pilot02 source proof input hash"),
])
def test_real_shallow_cli_rejects_missing_or_forged_proof(shallow, fault, message):
    path = shallow / PROOF
    if fault == "missing_file":
        path.unlink()  # Isolated disposable clone only; never repository evidence.
    else:
        proof = json.loads(gzip.decompress(path.read_bytes()))
        if fault == "missing_commit":
            del proof["git_objects"]["objects"][EXECUTION]
        elif fault == "object_bytes":
            entry = proof["git_objects"]["objects"][EXECUTION]
            raw = base64.b64decode(entry["base64"])+b"forged"
            entry["base64"] = base64.b64encode(raw).decode()
        elif fault == "envelope":
            proof["classification"] = "forged"
        else:
            if fault == "tree":
                proof["source"]["git"]["tree_sha"] = "0" * 40
            else:
                proof["source"]["inputs"][0]["sha256"] = "0" * 64
            proof["source"].pop("manifest_sha256")
            proof["source"] = seal(proof["source"], "manifest_sha256")
        if fault != "envelope":
            proof.pop("evidence_sha256")
            proof = seal(proof, "evidence_sha256")
        path.write_bytes(gzip.compress(json.dumps(proof).encode("utf-8"), mtime=0))
    result = cli_replay(shallow)
    assert result.returncode != 0
    assert message in result.stderr
    assert '"status": "PASS"' not in result.stdout
