"""Independently bind exact traversal receipts to raw body and speed samples."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIXES=('traversal_reference','traversal_contrast')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def rows(text):return [json.loads(line) for line in text.splitlines() if line.strip()]


def audit(index=None):
    index=index or json.loads((HERE/'update015-traversal-proof-index.json').read_text())
    require(index['selected'] is False and index['physical_acceptance_claimed'] is False and
            index['compatibility_passed']==index['process_saved_passed']==8 and
            len(index['cases'])==2,'Traversal exact matrix incomplete')
    manifest_path=HERE/'draft-traversal-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    require(manifest['runtime_manifest_sha256']==sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Runtime source changed')
    by_case={row['case_id']:row for row in manifest['cases']}
    counts={};joined=0;sampled=[]
    for suffix,case_row in zip(SUFFIXES,index['cases']):
        case_id=HERE.name+'__'+suffix
        require(case_row['case_id']==case_id and case_id in by_case,'Traversal case differs')
        construction=by_case[case_id]
        candidates=[{'id':'primary','construction':construction['construction'],
                     'construction_sha256':construction['construction_sha256']}]+construction['candidates']
        require([row['id'] for row in candidates]==list(CANDIDATES) and
                [row['candidate_id'] for row in case_row['candidates']]==list(CANDIDATES),
                'Traversal candidate inventory differs')
        require(len({row['construction_sha256'] for row in candidates})==4,
                'Traversal candidate constructions duplicate')
        require(len({(row['trigger']['source'],row['trigger']['metric'],
                     row['trigger']['failure_condition']) for row in candidates[1:]})==3,
                'Traversal fallback triggers duplicate')
        spec_path=HERE/f'update015-{suffix}-diagnostic.json'
        recipe_path=HERE/f'update015-{suffix}-recipe.json'
        recipe=json.loads(recipe_path.read_text())
        require(recipe['sources'][0]['sha256']==sha(spec_path),'Traversal recipe changed')
        spec=json.loads(spec_path.read_text())
        require([v['path'] for v in spec['videos']]==[name+'.mkv' for name in CAMERAS] and
                all(v['frames']==480 for v in spec['videos']),
                'Traversal source camera recipe differs')
        samples=rows(spec['files']['native_samples.jsonl'])
        frames=rows(spec['files']['video_frames.jsonl'])
        body=rows(spec['files']['body_history.jsonl'])
        trace=rows(spec['files']['trace.jsonl'])
        evidence=rows(spec['files']['capture/evidence.jsonl'])
        native=rows(spec['files']['capture/native/frames.jsonl'])
        survey=json.loads(spec['files']['road_geometry.json'])
        require(survey['intersection_polygon_xy_m']==[[-7,-7],[7,-7],[7,7],[-7,7]] and
                all(len(x)==480 for x in (samples,frames,body,trace,evidence,native)),
                'Traversal raw source inventory differs')
        moving=[];left=[]
        for i,(s,f,b,t,e,n) in enumerate(zip(samples,frames,body,trace,evidence,native)):
            require(s['video_frame']==f['video_frame']==i and
                    s['native_frame']==f['native_frame']==b['frame']==t['frame']==e['original_frame']==n['frame'] and
                    abs(s['time_s']-f['time_s'])<1e-6 and
                    abs(s['time_s']-t['time_s'])<1e-6 and
                    abs(s['time_s']-e['recording_time_s'])<1e-6 and
                    s['native_body_xy_m']==s['body_xy_m'] and
                    s['speed_provenance']==t['speed_provenance']==e['ego']['speed_provenance']=='synthetic_native_sample' and
                    s['speed_m_s']==t['speed_mps']==e['ego']['speed_mps'] and
                    s['two_way_native_survey'] is True,
                    'Traversal raw join or speed provenance differs')
            points=s['body_xy_m']
            if min(p[0] for p in points)>-7 and max(p[0] for p in points)<7 and s['speed_m_s']>.05:
                moving.append(i)
                if min(p[1] for p in points)>0:left.append(i)
            joined+=1
        require(moving and len(left)==(0 if suffix=='traversal_reference' else 39),
                'Traversal body contrast differs')
        counts[suffix]={'moving':len(moving),'moving_left':len(left)}
        sampled.append(samples)
        for expected,proof in zip(candidates,case_row['candidates']):
            folder=HERE/'update015-traversal-proofs'/suffix/expected['id']
            compat=json.loads((folder/'compatibility.json').read_text())
            saved=json.loads((folder/'process-saved.json').read_text())
            require(proof['case_id']==case_id and proof['candidate_id']==expected['id'] and
                    proof['selected'] is False and proof['synthetic_diagnostic'] is True and
                    proof['manifest_sha256']==sha(manifest_path) and
                    proof['recipe_sha256']==sha(recipe_path) and
                    proof['construction_sha256']==expected['construction_sha256']==sha(HERE/expected['construction']) and
                    proof['compatibility_sha256']==sha(folder/'compatibility.json') and
                    proof['process_saved_sha256']==sha(folder/'process-saved.json') and
                    proof['compatibility_log_sha256']==sha(folder/'compatibility.log') and
                    proof['process_saved_log_sha256']==sha(folder/'process-saved.log'),
                    'Traversal proof source binding differs')
            measured=compat['measurement_examples']['intersection_traversal']['value']
            require(compat['passed'] is True and compat['negative_removed']=='native_samples.jsonl' and
                    compat['fixture_manifest']['diagnostic-input.json']==sha(spec_path) and
                    measured['moving_traversal_frames']==len(moving) and
                    measured['moving_left_traversal_frames']==len(left) and
                    measured['legal_verdict'] is None and
                    saved['passed'] is True and saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames']==480 and
                    saved['final_video_checks']['passed'] is True and
                    saved['final_video_checks']['frames']==480 and
                    saved['missing_evidence'] is False and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Traversal exact receipt incomplete')
    require(all(a['native_center_xy_m'][0]==b['native_center_xy_m'][0]
                for a,b in zip(*sampled)),'Traversal longitudinal schedule differs')
    require(sampled[0][-1]['native_center_xy_m']==sampled[1][-1]['native_center_xy_m'],
            'Traversal parking endpoint differs')
    return {'raw_frame_joins_checked':joined,'exact_compatibility_passed':8,
            'exact_process_saved_passed':8,'counts':counts,'selected':False}


if __name__=='__main__':
    result=audit()
    original=json.loads((HERE/'update015-traversal-proof-index.json').read_text())
    rejected=0
    for damage in ('missing_candidate','false_selection','wrong_receipt'):
        altered=copy.deepcopy(original)
        if damage=='missing_candidate':altered['cases'][0]['candidates'].pop()
        elif damage=='false_selection':altered['selected']=True
        else:altered['cases'][0]['candidates'][0]['compatibility_sha256']='0'*64
        try:audit(altered)
        except (ValueError,KeyError):rejected+=1
        else:raise ValueError('Damaged traversal exact proof accepted')
    result['isolated_negative_rejections']=rejected
    print(json.dumps(result,sort_keys=True))
