"""Independently verify current-runtime offline construction matrix."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
FAMILIES=(('intersection','draft-execution-manifest.json',2),
          ('statutory','draft-statutory-execution-manifest.json',4),
          ('traversal','draft-traversal-execution-manifest.json',2))
CAMERAS=('overview','approach','reference_corner','driver_reference')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def audit(summary=None):
    summary=summary or json.loads((HERE/'update015-offline-summary.json').read_text())
    current=sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json')
    require(summary['runtime_manifest_sha256']==current,'Current runtime changed')
    require(summary['selected'] is False and len(summary['rows'])==32,'Offline matrix incomplete')
    expected=set();construction_hashes=set();cases=0
    for family,name,count in FAMILIES:
        path=HERE/name;manifest=json.loads(path.read_text())
        require(summary['manifest_sha256'][name]==sha(path),'Construction manifest changed')
        require(manifest['runtime_manifest_sha256']==current and len(manifest['cases'])==count,
                'Case family runtime or count changed')
        for case in manifest['cases']:
            cases+=1
            candidates=[{'id':'primary','construction':case['construction'],
                         'construction_sha256':case['construction_sha256']}]+case['candidates']
            require([item['id'] for item in candidates]==list(CANDIDATES),'Fallback order changed')
            require(len({item['construction_sha256'] for item in candidates})==4,
                    'Fallback constructions are not distinct')
            triggers=set()
            for item in candidates:
                candidate=item['id'];key=(family,case['case_id'],candidate)
                expected.add(key)
                construction_path=HERE/item['construction']
                require(item['construction_sha256']==sha(construction_path),'Construction source changed')
                construction_hashes.add(item['construction_sha256'])
                construction=json.loads(construction_path.read_text())
                files={file['path']:file['content'] for file in construction['files']}
                config=json.loads(files['config.json'])
                require(config['case_id']==case['case_id'] and config['candidate_id']==candidate,
                        'Bundled identity changed')
                require([camera['name'] for camera in config['cameras']]==list(CAMERAS),
                        'Current camera profile changed')
                if candidate!='primary':
                    trigger=item.get('trigger',{})
                    require(trigger.get('source') and trigger.get('metric') and
                            trigger.get('failure_condition'),'Fallback trigger incomplete')
                    triggers.add((trigger['source'],trigger['metric'],trigger['failure_condition']))
                row=next((row for row in summary['rows'] if
                          (row['family'],row['case_id'],row['candidate_id'])==key),None)
                require(row is not None and row['exit_code']==0,'Offline attempt failed')
                log=HERE/row['log']
                require(row['log_sha256']==sha(log) and '"offline_passed": true' in log.read_text().lower(),
                        'Offline receipt changed')
            require(len(triggers)==3,'Fallback triggers are not distinct')
    require(len(expected)==32 and len(construction_hashes)==32 and cases==8,
            'Case/candidate inventory changed')
    require({(r['family'],r['case_id'],r['candidate_id']) for r in summary['rows']}==expected,
            'Offline row inventory changed')
    return {'cases':cases,'exact_offline_passed':len(expected),'distinct_constructions':32,
            'three_distinct_fallback_triggers_per_case':True,'selected':False}


if __name__=='__main__':
    result=audit()
    original=json.loads((HERE/'update015-offline-summary.json').read_text())
    rejected=0
    for change in ('missing_row','false_selection','wrong_runtime'):
        damaged=copy.deepcopy(original)
        if change=='missing_row':damaged['rows'].pop()
        elif change=='false_selection':damaged['selected']=True
        else:damaged['runtime_manifest_sha256']='0'*64
        try:audit(damaged)
        except (ValueError,KeyError):rejected+=1
        else:raise ValueError('Independent audit accepted '+change)
    result['isolated_negative_rejections']=rejected
    print(json.dumps(result,sort_keys=True))
