"""Real current-main source entry in depth-one clones; no scientific execution."""

import json
import os
import subprocess
import sys

import pytest

from robust_budget_allocation.pilot.configuration import ROOT


@pytest.fixture
def checkout(tmp_path):
    folder = tmp_path / "source-entry"
    subprocess.run(["git", "clone", "--depth=1", "--no-local", "--single-branch",
        "-c", "core.autocrlf=false", ROOT.as_uri(), str(folder)], check=True, capture_output=True)
    assert subprocess.check_output(["git", "-C", str(folder), "rev-list", "--count", "HEAD"]).strip() == b"1"
    for name in ("src/robust_budget_allocation/pilot/execution.py",
                 "src/robust_budget_allocation/pilot/restart.py",
                 "src/robust_budget_allocation/pilot/replay.py",
                 "src/robust_budget_allocation/reproducibility/test_evidence.py"):
        assert (folder / name).read_bytes() == (ROOT / name).read_bytes(), "Commit implementation before entry tests"
    metadata = folder / "src/robust_budget_allocation.egg-info"
    metadata.mkdir()
    for name in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "requires.txt", "top_level.txt"):
        (metadata / name).write_text("ordinary packaging metadata\n", encoding="utf-8")
    return folder


PROGRAM = '''
import json
import sys
from pathlib import Path
from robust_budget_allocation.pilot.execution import source_gate
from robust_budget_allocation.pilot.restart import manifest, same_content
from robust_budget_allocation.pilot.replay import verify_source
from robust_budget_allocation.pilot.configuration import ROOT
from robust_budget_allocation.io.atomic import atomic_write_json
assert ROOT.resolve() == Path.cwd().resolve()
state = source_gate()
source = manifest()
path = Path(sys.argv[1])
atomic_write_json(path, source)
loaded = json.loads(path.read_text(encoding="utf-8"))
verify_source(loaded)
assert same_content(loaded, manifest())
assert same_content(state, source_gate())
print(json.dumps({"verified": True, "source": loaded}))
'''


def enter(folder, tmp_path):
    return subprocess.run([sys.executable, "-B", "-c", PROGRAM, str(tmp_path / "source.json")],
        cwd=folder, env=dict(os.environ, PYTHONPATH=str(folder / "src"),
                            GRB_LICENSE_FILE=str(tmp_path / "no-license")),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)


def test_real_depth_one_entry_metadata_and_persisted_source(checkout, tmp_path):
    result = enter(checkout, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verified"]
    assert not any(".egg-info/" in row["path"] for row in payload["source"]["inputs"])
    assert len(list((checkout / "src/robust_budget_allocation.egg-info").iterdir())) == 5
    assert not (checkout / "outputs").exists()
    assert not subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"]).strip()


@pytest.mark.parametrize("directory", ["src/robust_budget_allocation", "tests", "scripts", "configs"])
@pytest.mark.parametrize("ignored", [True, False])
def test_real_entry_rejects_protected_input(checkout, tmp_path, directory, ignored):
    relative = directory + "/unexpected_input.json"
    if ignored:
        with (checkout / ".git/info/exclude").open("a", encoding="utf-8") as handle:
            handle.write("\n/" + relative + "\n")
    (checkout / relative).write_text("{}", encoding="utf-8")
    result = enter(checkout, tmp_path)
    assert result.returncode != 0 and "untracked scientific inputs" in result.stderr
    assert relative in result.stderr


def test_real_entry_rejects_required_file_missing(checkout, tmp_path):
    (checkout / "requirements.txt").unlink()  # Disposable test clone only.
    result = enter(checkout, tmp_path)
    assert result.returncode != 0 and "tracked changes" in result.stderr


def test_real_entry_rejects_tracked_tampering(checkout, tmp_path):
    with (checkout / "requirements.txt").open("a", encoding="utf-8") as handle:
        handle.write("\n# test-only tampering\n")
    result = enter(checkout, tmp_path)
    assert result.returncode != 0 and "tracked changes" in result.stderr
