"""Independent source/receipt and controlled-pair audit of current CPU diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pair(reference, contrast):
    a,b = reference,contrast
    for key in ('assignment_id','law_id','cell_id','actor','rate_hz','frames',
                'road_sha256','camera_policy','requested_speed_mps',
                'pre_entry_dwell_s','circulation_direction'):
        require(a[key]==b[key], 'Current pair fixed condition changed: '+key)
    require(a['requested_lane_id']==-2 and b['requested_lane_id']==-1,
            'Current pair does not vary the governed lane request')
    require(a['controller_intention_sha256']!=b['controller_intention_sha256'],
            'Current pair intention identity collapsed')


def audit(matrix):
    index = json.loads((ROOT/'update015-current-candidate-index.json').read_text())
    require(matrix['candidate_index_sha256']==sha(ROOT/'update015-current-candidate-index.json'),
            'Current candidate index changed')
    items = {(x['case_id'].rsplit('__',1)[-1],x['candidate_id']):x
             for x in index['results']}
    rows = {(x['case_id'].rsplit('__',1)[-1],x['candidate_id']):x
            for x in matrix['results']}
    expected = {(case,candidate) for case in ('reference','contrast') for candidate in CANDIDATES}
    require(set(items)==expected and set(rows)==expected and len(matrix['results'])==8,
            'Current candidate coverage differs')
    config = {}
    for (case,candidate), item in items.items():
        row = rows[case,candidate]
        manifest = ROOT/item['manifest']
        require(sha(manifest)==item['manifest_sha256']==row['manifest_sha256'],
                'Current manifest changed')
        selected = json.loads(manifest.read_text())['cases'][0]
        selected = ({'construction':selected['construction'],
                     'construction_sha256':selected['construction_sha256']}
                    if candidate=='primary' else next(x for x in selected['candidates']
                                                      if x['id']==candidate))
        source = ROOT/selected['construction']
        require(sha(source)==selected['construction_sha256']==item['construction_sha256']
                ==row['construction_sha256'],'Current construction changed')
        construction = json.loads(source.read_text())
        files = {f['path']:f['content'] for f in construction['files']}
        config[case,candidate] = json.loads(files['config.json'])
        logdir = ROOT/'update015-current-all'/case/candidate
        compat_path, negative_path, processing_path = (
            logdir/'compatibility.json',logdir/'negative-analysis.log',logdir/'processing.json')
        require(all(p.is_file() for p in (compat_path,negative_path,processing_path)),
                'Current receipt missing')
        require(sha(compat_path)==row['compatibility_sha256'] and
                sha(negative_path)==row['negative_log_sha256'] and
                sha(processing_path)==row['processing_sha256'],
                'Current receipt changed')
        compat, processing = json.loads(compat_path.read_text()),json.loads(processing_path.read_text())
        require(compat.get('passed') is True and processing.get('passed') is True and
                compat.get('candidate_id')==processing.get('candidate_id')==candidate and
                compat.get('case_id')==processing.get('case_id')==item['case_id'] and
                compat.get('construction_sha256')==item['construction_sha256'] and
                processing.get('analysis_revision',{}).get('construction_sha256')==item['construction_sha256'],
                'Current receipt source or identity differs')
        require({'actual_analysis','native_validation','lean_decoder','render','final_decode',
                 'four_camera_sources','selected_measurements','negative_case_source'} <=
                set(compat.get('checks',[])), 'Current compatibility path incomplete')
        require(compat.get('negative_removed')=='native-raw-actors.jsonl' and
                'Missing required source: native-raw-actors.jsonl' in negative_path.read_text(),
                'Current missing-source negative absent')
        require(compat.get('analysis_sha256')==hashlib.sha256(
                files['finalize_current.py'].encode()).hexdigest() and
                processing.get('originals_preserved') is True and
                processing.get('missing_evidence') is False and
                processing.get('timestamp_joins',{}).get('frames')==240,
                'Current saved analyzer or frame proof differs')
        require(row['original_native_observed'] is False and
                processing.get('physical_acceptance_claimed') is False,
                'Current diagnostic overclaims original evidence')
    for candidate in CANDIDATES:
        pair(config['reference',candidate],config['contrast',candidate])
    negatives = {}
    damaged = copy.deepcopy(matrix)
    damaged['results'].pop()
    try:audit(damaged)
    except ValueError as error:negatives['missing_candidate']=str(error)
    damaged = copy.deepcopy(matrix)
    damaged['results'][0]['compatibility_sha256']='0'*64
    try:audit(damaged)
    except ValueError as error:negatives['stale_receipt']=str(error)
    damaged = copy.deepcopy(config['contrast','primary'])
    damaged['requested_speed_mps']+=1
    try:pair(config['reference','primary'],damaged)
    except ValueError as error:negatives['changed_fixed_speed']=str(error)
    if len(negatives)!=3:
        raise ValueError('Current negative controls failed')
    return {'format':'c132497-independent-current-cpu-audit-v1',
            'passed':True,'candidates':8,'controlled_pairs':4,
            'negative_rejections':negatives,'matrix_sha256':sha(ROOT/'update015-current-all-matrix.json'),
            'original_native_observed':False,'delivery_ready':False}


if __name__=='__main__':
    matrix = json.loads((ROOT/'update015-current-all-matrix.json').read_text())
    result = audit(matrix)
    output = ROOT/'update015-current-all-audit.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'candidates':8,'pairs':4,'audit_sha256':sha(output)}))
