"""Independently verify eight current right-turn offline constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def audit(summary=None):
    summary=summary or json.loads((HERE/'update015-offline-summary.json').read_text())
    manifest_path=HERE/'draft-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    require(summary['selected'] is False and summary['passed']==8 and len(summary['rows'])==8,
            'Right-turn offline matrix incomplete')
    require(summary['manifest_sha256']==sha(manifest_path) and
            summary['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']==
                sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Current right-turn manifest differs')
    expected=set();construction_hashes=set()
    for case in manifest['cases']:
        candidates=[{'id':'primary','construction':case['construction'],
                     'construction_sha256':case['construction_sha256']}]+case['candidates']
        require([row['id'] for row in candidates]==list(CANDIDATES),
                'Right-turn candidates differ')
        require(len({row['construction_sha256'] for row in candidates})==4,
                'Right-turn constructions duplicate')
        require(len({(row['trigger']['source'],row['trigger']['metric'],
                     row['trigger']['failure_condition']) for row in candidates[1:]})==3,
                'Right-turn fallback triggers duplicate')
        for candidate in candidates:
            key=(case['case_id'],candidate['id']);expected.add(key)
            path=HERE/candidate['construction']
            require(candidate['construction_sha256']==sha(path),
                    'Right-turn construction source differs')
            construction_hashes.add(sha(path))
            construction=json.loads(path.read_text())
            files={item['path']:item['content'] for item in construction['files']}
            config=json.loads(files['config.json'])
            require(config['case_id']==case['case_id'] and
                    config['candidate_id']==candidate['id'] and
                    [camera['name'] for camera in config['cameras']]==list(CAMERAS),
                    'Right-turn bundled camera or identity differs')
            row=next((row for row in summary['rows'] if
                      (row['case_id'],row['candidate_id'])==key),None)
            require(row is not None and row['exit_code']==0 and
                    row['construction_sha256']==candidate['construction_sha256'],
                    'Right-turn offline receipt missing')
            log=HERE/row['log']
            require(row['log_sha256']==sha(log) and '"offline_passed": true' in log.read_text().lower(),
                    'Right-turn offline log changed')
    require(len(manifest['cases'])==2 and len(expected)==len(construction_hashes)==8 and
            {(r['case_id'],r['candidate_id']) for r in summary['rows']}==expected,
            'Right-turn offline inventory differs')
    return {'cases':2,'exact_offline_passed':8,'distinct_constructions':8,
            'three_distinct_fallback_triggers_per_case':True,'selected':False}


if __name__=='__main__':
    result=audit()
    original=json.loads((HERE/'update015-offline-summary.json').read_text())
    rejected=0
    for damage in ('missing_row','false_selection','wrong_runtime'):
        altered=copy.deepcopy(original)
        if damage=='missing_row':altered['rows'].pop()
        elif damage=='false_selection':altered['selected']=True
        else:altered['runtime_manifest_sha256']='0'*64
        try:audit(altered)
        except (ValueError,KeyError):rejected+=1
        else:raise ValueError('Damaged right-turn offline proof accepted')
    result['isolated_negative_rejections']=rejected
    print(json.dumps(result,sort_keys=True))
