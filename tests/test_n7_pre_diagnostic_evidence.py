"""Read-only delivered diagnostics: independent accounting and real shallow CLI."""

import base64
from copy import deepcopy
import gzip
import json
import os
import statistics
import subprocess
import sys

import pytest

from robust_budget_allocation.algorithms.common import tolerance
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.mechanism_confirmation.audit import load_archive, same, verify_gate
from robust_budget_allocation.mechanism_confirmation.configuration import ROOT
from robust_budget_allocation.mechanism_confirmation.replay import replay_bundle
from robust_budget_allocation.pilot.storage import check_seal, seal

EVIDENCE='docs/evidence/N7_PRE_DIAGNOSTIC_EVIDENCE.json.gz'
EXECUTION='172b63716fa023d8fbb83193b2e4a06dba543eaf'


@pytest.fixture(scope='module')
def bundle():
    return load_archive(ROOT/EVIDENCE)


def near(a,b):
    assert abs(a-b) <= tolerance(a,b)


def test_all_90_replay_and_registered_stop(bundle):
    result=replay_bundle(bundle)
    assert result['status']=='PASS' and result['runs']==90 and result['completed_configs']==18
    assert result['gate']==dict(status='N7_PRE_OPTION_GATE_FAILED',cell_counts={'45':0,'90':0,'150':0},denominator=6)
    assert result['memory_decision']=='N7_PRE_MEMORY_NOT_IDENTIFIED'
    assert bundle['source']['git']['commit_sha']==EXECUTION
    assert bundle['source']['git']['tree_sha']=='fda896563268e97ed2e3e7492dd790a8d3852adf'
    for row in bundle['source']['inputs']:
        assert sha256_file(ROOT/row['path'])==row['sha256'], 'No production code/input change after execution'


def test_independent_1080_scenario_cash_and_physical_balances(bundle):
    count=0
    for saved in bundle['runs']:
        record=json.loads(saved['files']['record.json'])
        result=json.loads(saved['files']['result.json'])
        data=record['binding']['data']; rel=data['reliability']; base=rel['base']
        engine=result['engine']
        decision=engine['first_stage'] if 'first_stage' in engine else engine['incumbent']['first_stage']
        q=decision['q_by_level']; choice=decision['reliability_choice']; y=decision['y_F']
        cq=sum(base['unit_cost'][j]*sum(q[j].values()) for j in base['suppliers'])
        cr=sum(rel['fixed_premium'][j][choice[j]]+sum(rel['unit_premium'][j][k]*v for k,v in q[j].items()) for j in base['suppliers'])
        fee=data['option_fee']*y; first=cq+cr+fee
        for key,val in [('C_Q',cq),('C_R',cr),('option_fee',fee),('first_cost',first)]:
            near(result['mechanism'][key],val)
        losses=[]
        for row in result['mechanism']['scenarios']:
            w=row['scenario']; delivered=sum(rel['fulfillment'][w][j][k]*v for j in base['suppliers'] for k,v in q[j].items())
            e=data['emergency_price'][w]*row['g']; loss=e+base['shortage_penalty']*row['u']
            near(row['x']+row['u'],base['demand'][w])
            near(row['x']+row['h'],delivered+row['g'])
            near(row['delivered'],delivered); near(row['E'],e); near(row['loss'],loss)
            near(row['unused_budget'],base['budget']-first-e)
            assert first+e-base['budget'] <= tolerance(first+e,base['budget'])
            assert e-data['option_cap']*y <= tolerance(e,data['option_cap']*y)
            assert all(row[k] >= -tolerance(row[k],0) for k in ('x','u','h','g'))
            if y==0: near(row['g'],0); near(e,0)
            losses.append(loss); count+=1
        near(engine['objective'],first+max(losses))
    assert count==1080


def test_summary_manifest_and_memory_are_derived_not_unrun_zeroes(bundle):
    summary=json.loads((ROOT/'docs/evidence/N7_PRE_DIAGNOSTIC_SUMMARY.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'docs/evidence/N7_PRE_EXECUTION_MANIFEST.json').read_text(encoding='utf-8'))
    replay=json.loads((ROOT/'docs/evidence/N7_PRE_REPLAY.json').read_text(encoding='utf-8'))
    for x in (summary,manifest,replay): check_seal(x)
    assert summary['evidence_sha256']==sha256_file(ROOT/EVIDENCE)
    assert summary['observations']==bundle['observations'] and summary['diagnosis']==bundle['summary']
    assert replay['result']==replay_bundle(bundle)
    assert manifest['scientific_runs']==90 and manifest['completed_configs']==18 and not manifest['layer2_executed']
    records=[json.loads(r['files']['record.json']) for r in bundle['runs']]
    assert [r['run_id'] for r in manifest['runs']]==[r['run_id'] for r in records]
    for row,record,saved in zip(manifest['runs'],records,bundle['runs']):
        for key in ('method','seed','budget','status','certified','trace_sha256','output_sha256'):
            assert row[key]==(record['config'][key] if key in ('seed','budget') else record[key])
        assert row['file_manifest']==saved['manifest']
        assert same(record['source'],bundle['source'])
    near(summary['supervisor_total_seconds'],sum(r['watchdog']['wall_seconds'] for r in records))
    for m in ('M0','M1','EF','A0','A1'):
        values=[r['metrics']['algorithm_seconds'] for r in records if r['method']==m]
        assert summary['runtime'][m]==dict(min=min(values),median=statistics.median(values),max=max(values),total=sum(values))
    assert all(c['completed']==0 and c['seeds']==[] for c in summary['diagnosis']['cells'][3:])
    assert summary['a1_master_option_counts']=={'0':60,'1':0}
    assert summary['diagnosis']['all_opportunities']==0
    assert summary['later_nonterminal_iterations']==25
    assert all(not row['eligible_ids'] for o in bundle['observations'] for row in o['memory']['rows'])
    assert all(o['memory']['first_population_iteration']==1 for o in bundle['observations'])


def test_real_repair_and_prelaunch_evidence(bundle):
    repair=load_archive(ROOT/'docs/evidence/N7_PRE_REPAIR_VALIDATION.json.gz')
    check_seal(repair)
    assert repair['status']=='PASS' and repair['scientific_runs']==0
    assert repair['original_n0_n6_changed_paths']==[]
    assert repair['solver_free']==dict(tests=721,failures=0,errors=0,skipped=0)
    assert same(repair['source'],bundle['source'])
    verify_gate(bundle['gates'],bundle['source'])
    assert bundle['gates']['suites']['solver-free']['tests']==721
    assert bundle['gates']['suites']['licensed']['tests']==100


@pytest.fixture
def shallow(tmp_path):
    path=tmp_path/'delivery-depth-one'
    completed=subprocess.run(['git','clone','-c','core.autocrlf=false','--depth=1','--no-local',
        '--single-branch',ROOT.as_uri(),str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    assert completed.returncode==0,completed.stderr
    assert subprocess.check_output(['git','-C',str(path),'rev-list','--count','HEAD']).strip()==b'1'
    assert subprocess.run(['git','-C',str(path),'cat-file','-e',EXECUTION+'^{commit}'],capture_output=True).returncode!=0
    for name in (EVIDENCE,'scripts/n7_pre.py','src/robust_budget_allocation/mechanism_confirmation/audit.py'):
        assert (path/name).read_bytes()==(ROOT/name).read_bytes(), 'Commit delivery before shallow CLI test'
    return path


def cli(path):
    result=subprocess.run([sys.executable,'scripts/n7_pre.py','replay','--evidence',EVIDENCE],cwd=path,
        env=dict(os.environ,PYTHONPATH=str(path/'src'),GRB_LICENSE_FILE=str(path/'nonexistent-license')),
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    assert not (path/'outputs').exists()
    return result


def test_real_shallow_cli_replays_90_without_license_or_history(shallow):
    result=cli(shallow)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['runs']==90
    assert not subprocess.check_output(['git','-C',str(shallow),'status','--porcelain']).strip()


@pytest.mark.parametrize('fault', ['missing_object','tampered_object','inventory','forged_gate'])
def test_real_shallow_cli_rejects_forged_proof_or_diagnosis(shallow,fault):
    path=shallow/EVIDENCE; payload=load_archive(path)
    if fault=='missing_object': payload['git_objects'].pop(EXECUTION)
    elif fault=='tampered_object': payload['git_objects'][EXECUTION]['base64']=base64.b64encode(b'forged commit').decode()
    elif fault=='inventory':
        payload['source']['inputs'].pop()
        payload['source'].pop('manifest_sha256');payload['source']=seal(payload['source'],'manifest_sha256')
    else: payload['summary']['gate']['status']='N7_PRE_OPTION_GATE_PASSED'
    payload.pop('evidence_sha256');payload=seal(payload,'evidence_sha256')
    path.write_bytes(gzip.compress(json.dumps(payload).encode('utf-8'),mtime=0))  # disposable clone only
    result=cli(shallow)
    assert result.returncode!=0 and 'ValueError' in result.stderr
    assert '"status": "PASS"' not in result.stdout
