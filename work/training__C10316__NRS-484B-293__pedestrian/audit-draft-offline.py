"""Independent source, comparison, and receipt audit of eight C10316 bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    batch=json.loads((ROOT/'batch.json').read_text())
    assert manifest['runtime_manifest_sha256']==batch['runtime']['source_manifest_sha256']
    assert manifest['status']=='draft_not_selected' and len(manifest['cases'])==2
    summary=json.loads((HERE/'draft-offline-summary.json').read_text())
    assert summary['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
    assert len(summary['results'])==8
    all_configs=[]; seen=set()
    for case in manifest['cases']:
        validate(HERE,case,'NRS-484B-293','C10316',required=False,candidate_count=4)
        configs=[]
        for ident in ('primary','fallback1','fallback2','fallback3'):
            selected=case if ident=='primary' else next(x for x in case['candidates'] if x['id']==ident)
            path=HERE/selected['construction']
            assert sha(path)==selected['construction_sha256']
            construction=json.loads(path.read_text())
            files={item['path']:item['content'] for item in construction['files']}
            for name in ('runner.py','geometry.py','engineering.py','measure_crosswalk.py','fallback_triggers.py','finalize.py','road.xodr'):
                assert files[name]==(HERE/'native'/name).read_text()
            assert files['tests/test_offline.py']==(HERE/'native/test_offline.py').read_text()
            config=json.loads(files['config.json'])
            assert config['case_id']==case['case_id']==config['selected_case_id']
            assert config['candidate_id']==ident and config['duration_s']==12 and config['rate_hz']==20
            assert config['required_atoms']==['ru.pedestrian','kin.position','kin.heading','st.crosswalk','rel.occupies']
            assert [camera['name'] for camera in config['cameras']]==[
                'overview','approach','reference_corner','driver_reference']
            assert config['actor']=='pedestrian' and config['law_id']=='NRS-484B-293'
            configs.append(config)
            receipt=json.loads((path.parent/'draft-receipt.json').read_text())
            assert receipt['case_id']==case['case_id'] and receipt['candidate_id']==ident
            assert receipt['construction_sha256']==selected['construction_sha256']
            assert receipt['exit_code']==0
            assert sha(HERE/receipt['command_log'])==receipt['command_log_sha256']
            assert sha(HERE/receipt['unit_log'])==receipt['unit_log_sha256']
            log=(HERE/receipt['unit_log']).read_text()
            assert 'Ran 6 tests' in log and '\nOK' in log
            assert 'simulation_started' in (HERE/receipt['command_log']).read_text()
            assert receipt in summary['results']
            seen.add((case['case_id'],ident))
        base=configs[0]
        for other in configs[1:]:
            compared=dict(other);compared['candidate_id']='primary'
            assert compared==base
        all_configs.append(configs)
    assert len(seen)==8
    for a,b in zip(*all_configs):
        ca=dict(a);cb=dict(b)
        for c in (ca,cb):
            c.pop('case_id');c.pop('selected_case_id');c.pop('case');c.pop('case_suffix')
        assert ca==cb
    print(json.dumps({'audit':'pass','cases':2,'exact_offline_bundles':8,
                      'runtime_hash_bound':True,'selected_cases':0},sort_keys=True))


if __name__=='__main__':main()
