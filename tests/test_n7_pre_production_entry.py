"""Actual committed production entry in real depth-one clones; no monkeypatch.

The persisted gate fixture is synthetic engineering input, NOT license evidence.
Actual licensed prelaunch is a separate production command after these tests pass.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from robust_budget_allocation.mechanism_confirmation.configuration import ROOT


@pytest.fixture
def entry_clone(tmp_path):
    folder = tmp_path / 'entry-depth-one'
    result = subprocess.run(['git','clone','-c','core.autocrlf=false','--depth=1',
        '--no-local','--single-branch',ROOT.as_uri(),str(folder)],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    assert result.returncode == 0, result.stderr
    for name in ('src/robust_budget_allocation/mechanism_confirmation/audit.py',
                 'src/robust_budget_allocation/mechanism_confirmation/execution.py'):
        assert (folder/name).read_bytes() == (ROOT/name).read_bytes(), 'Commit repair before testing production clone'
    assert subprocess.check_output(['git','-C',str(folder),'rev-list','--count','HEAD']).strip() == b'1'
    metadata = folder/'src/robust_budget_allocation.egg-info'
    metadata.mkdir()
    for name in ('PKG-INFO','SOURCES.txt','dependency_links.txt','requires.txt','top_level.txt'):
        (metadata/name).write_text('normal packaging metadata\n',encoding='utf-8')
    assert not subprocess.check_output(['git','-C',str(folder),'status','--porcelain']).strip()
    return folder


def entry(folder, program):
    env = dict(os.environ, PYTHONPATH=str(folder/'src'), GRB_LICENSE_FILE=str(folder/'unavailable-license'))
    return subprocess.run([sys.executable,'-c',program],cwd=folder,env=env,capture_output=True,
        text=True,encoding='utf-8',errors='replace',timeout=120)


SOURCE = '''
import json
from robust_budget_allocation.mechanism_confirmation.audit import source, proof, verify_source
from robust_budget_allocation.mechanism_confirmation.configuration import registration
registration()
manifest = source()
verify_source(manifest, proof(manifest))
print(json.dumps(manifest))
'''


def test_real_production_source_accepts_normal_sibling_metadata(entry_clone):
    result=entry(entry_clone,SOURCE)
    assert result.returncode == 0, result.stderr
    manifest=json.loads(result.stdout)
    assert not manifest['git']['tracked_dirty']
    assert not any('.egg-info/' in r['path'] for r in manifest['inputs'])
    assert len(list((entry_clone/'src/robust_budget_allocation.egg-info').iterdir())) == 5
    assert not (entry_clone/'outputs').exists()


@pytest.mark.parametrize('directory', ['src/robust_budget_allocation','tests','scripts','configs'])
@pytest.mark.parametrize('ignored', [False,True])
def test_real_production_source_rejects_scientific_pollution(entry_clone,directory,ignored):
    relative=directory+'/unregistered_scientific_input.json'
    if ignored:
        with (entry_clone/'.git/info/exclude').open('a',encoding='utf-8') as handle:
            handle.write('\n/'+relative+'\n')
    (entry_clone/relative).write_text('{"unregistered":true}',encoding='utf-8')
    result=entry(entry_clone,SOURCE)
    assert result.returncode != 0
    assert 'untracked scientific inputs' in result.stderr and relative in result.stderr
    assert not (entry_clone/'outputs').exists()


@pytest.mark.parametrize('name', ['scripts/n7_pre.py','src/robust_budget_allocation/models/m0.py'])
def test_real_production_source_rejects_missing_required_file(entry_clone,name):
    (entry_clone/name).unlink()  # Isolated temporary clone only.
    result=entry(entry_clone,SOURCE)
    assert result.returncode != 0
    assert 'tracked changes' in result.stderr or 'No module named' in result.stderr


def test_real_production_source_rejects_tracked_tampering(entry_clone):
    with (entry_clone/'src/robust_budget_allocation/models/m0.py').open('a',encoding='utf-8') as handle:
        handle.write('\n# uncommitted scientific tampering\n')
    result=entry(entry_clone,SOURCE)
    assert result.returncode != 0 and 'tracked changes' in result.stderr


def test_real_persisted_gate_roundtrip_and_forgery_rejection(entry_clone):
    result=entry(entry_clone, '''
import json
from robust_budget_allocation.mechanism_confirmation.audit import source,proof,same,load_archive
from robust_budget_allocation.mechanism_confirmation.execution import GATES,validate_gates
from robust_budget_allocation.mechanism_confirmation.configuration import ROOT,FROZEN
from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.pilot.storage import seal
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.mechanism_confirmation.audit import inputs
GATES.mkdir(parents=True)
manifest=source()
assert same(manifest,build_source_manifest(ROOT,input_paths=inputs()))
payload=dict(status='PASS',source=manifest,git_objects=proof(manifest),frozen_hashes=FROZEN,
    test_fixture_only=True,environment=load_archive(ROOT/'docs/evidence/N6_PILOT02_EVIDENCE.json.gz')['gates']['environment'],
    suites={},xml_files={})
for name in ('solver-free','licensed'):
    raw='<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"/></testsuites>'
    path=GATES/(name+'.xml'); path.write_text(raw,encoding='utf-8')
    payload['xml_files'][name]=path.read_bytes().decode('utf-8')
    payload['suites'][name]=dict(tests=1,failures=0,errors=0,skipped=0,returncode=0,xml_sha256=sha256_file(path))
atomic_write_json(GATES/'gates.json',seal(payload))
assert same(validate_gates()['source'],manifest)
# Change full content and recompute seals: a saved digest is not sufficient.
payload['source']['packages']['Pyomo']='forged'
payload['source'].pop('manifest_sha256')
payload['source']=seal(payload['source'],'manifest_sha256')
atomic_write_json(GATES/'gates.json',seal(payload))
try:
    validate_gates()
except ValueError as exc:
    assert 'source/registration' in str(exc)
else:
    raise AssertionError('forged source accepted')
assert not (ROOT/'outputs/n7_pre').exists()
print('production persisted JSON validation PASS; forged full source rejected; NO SOLVE')
''')
    assert result.returncode == 0, result.stderr
    assert 'NO SOLVE' in result.stdout
