"""Independent exact-bundle and pinned offline receipt audit for 3(a)."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate,verify_report
CANDIDATES={'primary','fallback1','fallback2','fallback3'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    summary=json.loads((FOLDER/'draft-offline-summary.json').read_text())
    policy=json.loads((FOLDER/'draft-construction/candidate-manifest.json').read_text())
    assert manifest['status']=='draft_not_selected'
    assert manifest['assignment_id']==policy['assignment_id']
    assert manifest['runtime_manifest_sha256']==summary['runtime_manifest_sha256']
    assert len(manifest['cases'])==2 and len(summary['results'])==8
    seen=set()
    for entry in manifest['cases']:
        case_id=entry['case_id']
        assert case_id.startswith(manifest['assignment_id']+'__')
        assert entry['measurement_procedure']['entrypoint']=='finalize.py'
        contract=json.loads((FOLDER/entry['measurement_contract']).read_text())
        plan=json.loads((FOLDER/'case-plan.json').read_text())
        validate(contract,plan['requirement_dispositions'],(FOLDER/'native/finalize.py').read_text(),case_id)
        suffix=case_id.split('__')[-1]
        fixture=FOLDER/'synthetic-local'/suffix
        verify_report(contract,json.loads((fixture/'finalizer-analysis-report.json').read_text()),fixture)
        refs=[{'id':'primary','construction':entry['construction'],
               'construction_sha256':entry['construction_sha256']},*entry['candidates']]
        assert {r['id'] for r in refs}==CANDIDATES
        for ref in refs:
            key=(case_id,ref['id']);assert key not in seen;seen.add(key)
            path=FOLDER/ref['construction']
            assert sha(path)==ref['construction_sha256']
            construction=json.loads(path.read_text())
            assert construction['case_id']==case_id
            assert construction['entrypoint']=='runner.py'
            assert construction['status']=='unselected_cpu_draft'
            files={f['path']:f['content'] for f in construction['files']}
            assert {'runner.py','geometry.py','controller.py','engineering.py',
                    'survey.py','cameras.py','measure_saved.py','finalize.py','tests/test_constructions.py',
                    'config.json'}<=set(files)
            runner=files['runner.py']
            assert runner.index('frame=world.tick()') < runner.index('observed_speed=observed_speed_mps(ego)')
            assert '"native_body_xy_m":body,"speed_mps":observed_speed' in runner
            config=json.loads(files['config.json'])
            assert config['case_id']==case_id and config['candidate_id']==ref['id']
            assert config['duration_s']==24 and config['rate_hz']==20
            for name,content in files.items():
                if name=='config.json':continue
                assert (FOLDER/'native'/Path(name).name).read_text()==content
            if ref['id']!='primary':
                expected=next(row['trigger'] for row in policy['cases'] if
                              row['case_id']==case_id and row['candidate_id']==ref['id'])
                assert ref['trigger']==expected
    assert len(seen)==8
    receipts={(r['case_id'],r['candidate_id']):r for r in summary['results']}
    assert set(receipts)==seen
    for key,receipt in receipts.items():
        assert receipt['exit_code']==0
        assert 'runtime.py offline' in receipt['command']
        assert receipt['construction_sha256']==next(
            r['construction_sha256'] for e in manifest['cases'] if e['case_id']==key[0]
            for r in [{'id':'primary','construction_sha256':e['construction_sha256']},*e['candidates']]
            if r['id']==key[1])
        for field,hash_field in (('command_log','command_log_sha256'),('unit_log','unit_log_sha256')):
            assert sha(FOLDER/receipt[field])==receipt[hash_field]
        unit=(FOLDER/receipt['unit_log']).read_text()
        assert 'Ran 4 tests' in unit and '\nOK\n' in unit
        assert '"native_imported": false' in unit
    return {'passed':True,'cases':2,'exact_unselected_bundles':8,
            'offline_tests_per_bundle':4,'selected_or_physical_claimed':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
