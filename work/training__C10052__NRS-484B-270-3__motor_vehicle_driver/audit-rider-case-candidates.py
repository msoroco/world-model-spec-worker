"""Independent exact bundle inventory and changed-source rejection audit."""
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
    manifest_path=HERE/'draft-rider-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    proof=json.loads((HERE/'rider-case-offline-summary.json').read_text())
    assert proof['manifest_sha256']==sha(manifest_path)
    assert len(manifest['cases'])==6 and len(proof['results'])==24
    rows=[]
    for entry in manifest['cases']:
        case_id=entry['case_id']
        reference=None
        for name in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if name=='primary' else next(c for c in entry['candidates'] if c['id']==name)
            path=HERE/ref['construction']
            assert sha(path)==ref['construction_sha256']
            _,_,bundle=select(manifest_path,case_id,name)
            files={x['path']:x['content'] for x in bundle['files']}
            config=json.loads(files['config.json'])
            assert config['case_id']==case_id and config['candidate_id']==name
            rider=config['rider_type']
            assert 'ru.'+rider in config['required_atoms']
            assert 'ru.'+rider in config['mandatory_channels']
            assert 'rider_actor.type_id!=asset_ids[rider_type]' in files['runner.py']
            assert 'rider_file.write(json.dumps(rider_row' in files['runner.py']
            assert 'rider_geometry.json' in files['runner.py']
            assert 'engineering=parameters(rider_type,response,candidate)' in files['runner.py']
            assert files['rider_candidates.py']==(HERE/'native/rider_candidates.py').read_text()
            assert 'measure_rider_native.py' in files
            assert 'original_native' in files['measure_rider_native.py']
            assert 'finalize_rider.py' in files
            assert "source.get('source_kind')=='original_native'" in files['finalize_rider.py']
            assert "source.get('source_kind')=='synthetic_native_shaped_diagnostic'" in files['finalize_rider.py']
            check=next(x for x in proof['results'] if x['case_id']==case_id and x['candidate_id']==name)
            assert check['construction_sha256']==ref['construction_sha256']
            assert check['exit_code']==0 and sha(HERE/check['command_log'])==check['command_log_sha256']
            assert sha(ROOT/check['unit_log'])==check['unit_log_sha256']
            knobs={key:config.get(key) for key in ('rider_type','rider_response')}
            if name=='primary':reference=knobs
            else:assert knobs==reference
            rows.append({'case_id':case_id,'candidate_id':name,'construction_sha256':sha(path),
                         'offline_log_sha256':check['unit_log_sha256']})
    # Exact selection must refuse a changed construction digest.
    first=manifest['cases'][0]
    altered=json.loads(json.dumps(manifest))
    altered['cases'][0]['construction_sha256']='0'*64
    temp=HERE/'draft-rider-changed-source-negative-manifest.json'
    temp.write_text(json.dumps(altered,indent=2)+'\n')
    rejected=False
    try:select(temp,first['case_id'],'primary')
    except ValueError as exc:rejected='Candidate construction changed' in str(exc)
    finally:temp.unlink()
    assert rejected
    package_path=HERE/'rider-package-matrix-summary.json'
    package=json.loads(package_path.read_text())
    assert package['passed'] is True and package['manifest_sha256']==sha(manifest_path)
    assert len(package['results'])==24
    result={'format':'c10052-exact-rider-independent-audit-v1','passed':True,
            'manifest_sha256':sha(manifest_path),'offline_summary_sha256':sha(HERE/'rider-case-offline-summary.json'),
            'synthetic_v1_package_matrix_sha256':sha(package_path),
            'cases':6,'candidates':24,'changed_construction_rejected':True,
            'original_native_capture_executed':False,
            'synthetic_v1_package_compatibility_proven':True,
            'strict_v2_package_compatibility_proven':False,
            'selected':False,'rows':rows}
    (HERE/'rider-case-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':main()
