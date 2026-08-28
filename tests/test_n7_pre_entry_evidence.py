"""Post-stop read-only evidence tests, not prelaunch or scientific retries."""

import json
from pathlib import Path

import pytest

from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.mechanism_confirmation.audit import load_archive, verify_source
from robust_budget_allocation.mechanism_confirmation.configuration import ROOT, FROZEN
from robust_budget_allocation.pilot.storage import check_seal, safe_relative
from robust_budget_allocation.reproducibility.git_state import validate_source_state


def test_entry_failure_does_not_claim_scientific_outcomes():
    evidence = json.loads((ROOT/'docs/evidence/N7_PRE_ENTRY_FAILURE.json').read_text(encoding='utf-8'))
    assert evidence['returncode'] == 1 and evidence['scientific_runs'] == evidence['completed_configs'] == 0
    assert not evidence['gates_directory_exists'] and not evidence['batch_directory_exists']
    assert not evidence['retry_performed'] and not evidence['packaging_files_deleted']
    assert evidence['exception_type'] == 'RuntimeError'
    assert len(evidence['files']) == 5
    assert evidence['prelaunch_suites'] == 'NOT_STARTED' and evidence['preflight'] == 'NOT_RUN'


def test_entry_code_proof_authenticates_attempt_not_gate_success():
    payload = load_archive(ROOT/'docs/evidence/N7_PRE_ENTRY_SOURCE.json.gz')
    check_seal(payload)
    verify_source(payload['source'], payload['git_objects'])
    assert payload['source']['git']['commit_sha'] == '21e217a974e82027364494b2a2342562786ed526'
    assert payload['source']['git']['tree_sha'] == 'f577262b7838976878c28dffe7e6a244a03dabba'
    assert not payload['source']['git']['tracked_dirty']
    assert 'NOT successful source validation' in payload['purpose']


def test_ignored_editable_metadata_reproduces_gate_rejection(tmp_path):
    import subprocess
    def git(*args):
        return subprocess.run(['git','-C',str(tmp_path),*args],check=True,capture_output=True)
    git('init'); git('config','user.name','test'); git('config','user.email','test@example.invalid')
    (tmp_path/'.gitignore').write_text('*.egg-info/\n')
    code=tmp_path/'src/pkg/model.py'; code.parent.mkdir(parents=True); code.write_text('# fixture\n')
    git('add','.'); git('commit','-m','fixture')
    metadata=tmp_path/'src/pkg.egg-info/PKG-INFO'; metadata.parent.mkdir(); metadata.write_text('metadata\n')
    assert git('status','--porcelain').stdout == b''
    with pytest.raises(RuntimeError, match='untracked scientific inputs.*egg-info'):
        validate_source_state(tmp_path,required_tracked_paths=[code],scientific_roots=('src',))
    assert metadata.read_text() == 'metadata\n'  # no deletion/workaround


def test_complete_delivery_inventory_and_hashes():
    expected = set(FROZEN) | {
        'scripts/n7_pre.py', 'tests/test_n7_pre.py', 'tests/test_n7_pre_entry_evidence.py',
        'docs/N7_PRE_MECHANISM_REPORT.md', 'docs/N7_PRE_MEMORY_DIAGNOSIS.md',
        'docs/N7_PRE_DELIVERY_MANIFEST.json', 'docs/evidence/N7_PRE_ENTRY_FAILURE.json',
        'docs/evidence/N7_PRE_ENTRY_SOURCE.json.gz',
    } | {'src/robust_budget_allocation/mechanism_confirmation/'+n+'.py' for n in
         ('__init__','audit','configuration','diagnosis','execution','replay')}
    manifest=json.loads((ROOT/'docs/N7_PRE_DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
    assert len(manifest['files']) == len(set(manifest['files']))
    assert set(manifest['files']) == expected
    rows=[line.split('  ',1) for line in (ROOT/'docs/N7_PRE_HASHES.sha256').read_text().splitlines()]
    assert len(rows) == len(expected) and {r[1] for r in rows} == expected
    for digest, name in rows:
        assert safe_relative(name) == name
        path=ROOT/name
        assert path.is_file() and not path.is_symlink() and sha256_file(path) == digest
