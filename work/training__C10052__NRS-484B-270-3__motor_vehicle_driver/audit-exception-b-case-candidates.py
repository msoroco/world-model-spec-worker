"""Independent exact exception-b bundle, offline receipt and tamper audit."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import select


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path=HERE/'draft-exception-b-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    offline=json.loads((HERE/'exception-b-case-offline-summary.json').read_text())
    assert offline['passed'] and offline['manifest_sha256']==sha(manifest_path)
    assert len(manifest['cases'])==2 and len(offline['results'])==8
    rows=[]
    for entry in manifest['cases']:
        case_id=entry['case_id']
        suffix=case_id.rsplit('__',1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            path=HERE/ref['construction']
            assert sha(path)==ref['construction_sha256']
            _,_,bundle=select(manifest_path,case_id,candidate)
            files={x['path']:x['content'] for x in bundle['files']}
            config=json.loads(files['config.json'])
            assert config['case_id']==case_id and config['candidate_id']==candidate
            assert config['case_suffix']==suffix and config['rider_type']=='disabled_vehicle'
            names=[channel['name'] for channel in config['recording_description']['channels']]
            assert len(names)==len(set(names)) and 'ru.bicycle' not in names and 'ru.pedestrian' not in names and 'ru.vehicle' not in names
            runner=files['runner.py']
            assert "fault_readback,_=apply_fault(ego,True)" in runner
            assert 'exception_b_native_samples.jsonl' in runner
            assert 'exception-b-source-manifest.json' in runner
            for module in ('exception_b_engineering','exception_b_geometry','exception_b_native','finalize_exception_b'):
                assert files[module+'.py']==(HERE/'native'/(module+'.py')).read_text()
            receipt=next(x for x in offline['results'] if x['case_id']==case_id and x['candidate_id']==candidate)
            assert receipt['exit_code']==0 and receipt['simulation_started'] is False
            assert receipt['construction_sha256']==ref['construction_sha256']
            assert sha(HERE/receipt['command_log'])==receipt['command_log_sha256']
            assert sha(ROOT/receipt['unit_log'])==receipt['unit_log_sha256']
            rows.append({'case_id':case_id,'candidate_id':candidate,
                         'construction_sha256':sha(path),
                         'offline_log_sha256':receipt['unit_log_sha256']})
    # Selection cannot silently accept a changed construction digest.
    altered=json.loads(json.dumps(manifest))
    altered['cases'][0]['construction_sha256']='0'*64
    temporary=HERE/'draft-exception-b-changed-source-negative-manifest.json'
    temporary.write_text(json.dumps(altered,indent=2)+'\n')
    rejected=False
    try:select(temporary,manifest['cases'][0]['case_id'],'primary')
    except ValueError as exc:rejected='Candidate construction changed' in str(exc)
    finally:temporary.unlink()
    assert rejected
    result={'format':'c10052-exact-exception-b-independent-audit-v1',
            'passed':True,'manifest_sha256':sha(manifest_path),
            'offline_summary_sha256':sha(HERE/'exception-b-case-offline-summary.json'),
            'cases':2,'candidates':8,'changed_construction_rejected':True,
            'original_native_capture_executed':False,
            'synthetic_v1_package_compatibility_proven':False,
            'strict_v2_package_compatibility_proven':False,
            'selected':False,'rows':rows}
    (HERE/'exception-b-case-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':main()
