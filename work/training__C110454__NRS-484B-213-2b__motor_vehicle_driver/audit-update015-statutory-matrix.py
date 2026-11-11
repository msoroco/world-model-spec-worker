"""Independently bind exact statutory receipts to four raw diagnostic branches."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIXES=('rail_reference','rail_contrast','oneway_absent','oneway_present')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CAMERAS=('overview','approach','reference_corner','driver_reference')
EXPECTED={'rail_reference':('railroad_crossing',False,'outside_100_ft',-20.0),
          'rail_contrast':('railroad_crossing',False,'within_100_ft',-20.0),
          'oneway_absent':('intersection',False,'within_100_ft',-7.0),
          'oneway_present':('intersection',True,'within_100_ft',-7.0)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def audit(index=None):
    index=index or json.loads((HERE/'update015-statutory-proof-index.json').read_text())
    require(index['selected'] is False and index['physical_acceptance_claimed'] is False and
            index['compatibility_passed']==index['process_saved_passed']==16 and
            len(index['cases'])==4,'Statutory exact matrix incomplete')
    manifest_path=HERE/'draft-statutory-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    require(manifest['runtime_manifest_sha256']==sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Runtime source changed')
    construction_by_case={item['case_id']:item for item in manifest['cases']}
    relations={};joined=0
    for suffix,case_row in zip(SUFFIXES,index['cases']):
        case_id=HERE.name+'__'+suffix
        require(case_row['case_id']==case_id and case_id in construction_by_case,
                'Case identity differs')
        construction=construction_by_case[case_id]
        candidates=[{'id':'primary','construction':construction['construction'],
                     'construction_sha256':construction['construction_sha256']}]+construction['candidates']
        require([row['id'] for row in candidates]==list(CANDIDATES) and
                [row['candidate_id'] for row in case_row['candidates']]==list(CANDIDATES),
                'Candidate inventory differs')
        require(len({row['construction_sha256'] for row in candidates})==4,
                'Candidate constructions duplicate')
        triggers={(row['trigger']['source'],row['trigger']['metric'],
                   row['trigger']['failure_condition']) for row in candidates[1:]}
        require(len(triggers)==3,'Fallback triggers duplicate')
        spec_path=HERE/f'update015-{suffix}-diagnostic.json'
        recipe_path=HERE/f'update015-{suffix}-recipe.json'
        recipe=json.loads(recipe_path.read_text())
        require(recipe['sources'][0]['sha256']==sha(spec_path),
                'Recipe source hash differs')
        spec=json.loads(spec_path.read_text())
        require([v['path'] for v in spec['videos']]==[name+'.mkv' for name in CAMERAS] and
                all(v['frames']==480 for v in spec['videos']),
                'Statutory source camera recipe differs')
        sample=rows(spec['files']['native_samples.jsonl'])
        frames=rows(spec['files']['video_frames.jsonl'])
        body=rows(spec['files']['body_history.jsonl'])
        trace=rows(spec['files']['trace.jsonl'])
        evidence=rows(spec['files']['capture/evidence.jsonl'])
        native=rows(spec['files']['capture/native/frames.jsonl'])
        require(all(len(x)==480 for x in (sample,frames,body,trace,evidence,native)),
                'Statutory raw frame inventory incomplete')
        zone,one_way,expected_relation,boundary=EXPECTED[suffix]
        context=json.loads(spec['files']['statutory_context.json'])
        survey=json.loads(spec['files']['road_geometry.json'])
        require(context['zone_kind']==zone and context['one_way'] is one_way and
                context['boundary_x_m']==survey['approach_boundary_x_m']==boundary and
                context['railroad_crossing'] is suffix.startswith('rail_') and
                survey['one_way_native_readback'] is one_way and
                survey['road_directions_native']['approach_opposing']==([1,0] if one_way else [-1,0]),
                'Statutory road or exception context differs')
        left=[]
        for i,(s,f,b,t,e,n) in enumerate(zip(sample,frames,body,trace,evidence,native)):
            require(s['video_frame']==f['video_frame']==i and
                    s['native_frame']==f['native_frame']==b['frame']==t['frame']==e['original_frame']==n['frame'] and
                    abs(s['time_s']-f['time_s'])<1e-6 and
                    abs(s['time_s']-t['time_s'])<1e-6 and
                    abs(s['time_s']-e['recording_time_s'])<1e-6 and
                    abs(s['time_s']-n['time_s'])<1e-6 and
                    s['native_body_xy_m']==s['body_xy_m'] and
                    s['one_way_native_survey'] is one_way and
                    s['two_way_native_survey'] is (not one_way) and
                    s['speed_provenance']==t['speed_provenance']==e['ego']['speed_provenance']=='synthetic_native_sample' and
                    s['speed_m_s']==t['speed_mps']==e['ego']['speed_mps'],
                    'Statutory raw join or speed provenance differs')
            vertices=s['body_xy_m']
            if min(p[1] for p in vertices)>0 and max(p[0] for p in vertices)<boundary and s['speed_m_s']>.05:
                left.append(boundary-max(p[0] for p in vertices))
            joined+=1
        require(left,'No statutory left-side approach interval')
        nearest=min(left)
        relation='within_100_ft' if nearest<30.48 else 'outside_100_ft'
        require(relation==expected_relation,'Statutory sampled relation differs')
        relations[suffix]=relation
        for expected,proof in zip(candidates,case_row['candidates']):
            folder=HERE/'update015-statutory-proofs'/suffix/expected['id']
            compat=json.loads((folder/'compatibility.json').read_text())
            saved=json.loads((folder/'process-saved.json').read_text())
            construction_data=json.loads((HERE/expected['construction']).read_text())
            road_text=next(item['content'] for item in construction_data['files']
                           if item['path']=='road.xodr')
            road_sha=hashlib.sha256(road_text.encode()).hexdigest()
            require(proof['case_id']==case_id and proof['candidate_id']==expected['id'] and
                    proof['selected'] is False and proof['synthetic_diagnostic'] is True and
                    proof['manifest_sha256']==sha(manifest_path) and
                    proof['recipe_sha256']==sha(recipe_path) and
                    proof['construction_sha256']==expected['construction_sha256']==sha(HERE/expected['construction']) and
                    proof['compatibility_sha256']==sha(folder/'compatibility.json') and
                    proof['process_saved_sha256']==sha(folder/'process-saved.json') and
                    proof['compatibility_log_sha256']==sha(folder/'compatibility.log') and
                    proof['process_saved_log_sha256']==sha(folder/'process-saved.log'),
                    'Statutory proof source binding differs')
            measured=compat['measurement_examples']['statutory_approach_relation']['value']
            context_value=compat['measurement_examples']['statutory_approach_relation']['statutory_context']
            require(compat['passed'] is True and compat['negative_removed']=='statutory_context.json' and
                    compat['fixture_manifest']['diagnostic-input.json']==sha(spec_path) and
                    measured['sampled_relation']==relation and
                    abs(measured['nearest_body_front_to_zone_m']-nearest)<1e-5 and
                    measured['one_way_native_survey'] is one_way and
                    measured['zone_kind']==zone and measured['legal_verdict'] is None and
                    context_value['authored_road_sha256']==road_sha,
                    'Statutory measured receipt differs')
            require(context_value['zone_kind']==zone and context_value['one_way'] is one_way and
                    context_value['legal_verdict'] is None and
                    saved['passed'] is True and saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames']==480 and
                    saved['final_video_checks']['passed'] is True and
                    saved['final_video_checks']['frames']==480 and
                    saved['missing_evidence'] is False and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Statutory saved receipt incomplete')
            if suffix.startswith('oneway_'):
                exception=compat['measurement_examples']['statutory_context']['value']
                require(exception['one_way'] is one_way and
                        exception['applicability']=='requires_independent_review' and
                        exception['legal_verdict'] is None,
                        'One-way exception context claimed legal resolution')
    return {'raw_frame_joins_checked':joined,'exact_compatibility_passed':16,
            'exact_process_saved_passed':16,'relations':relations,'selected':False}


if __name__=='__main__':
    result=audit()
    original=json.loads((HERE/'update015-statutory-proof-index.json').read_text())
    rejected=0
    for damage in ('missing_candidate','false_selection','wrong_receipt'):
        altered=copy.deepcopy(original)
        if damage=='missing_candidate':altered['cases'][0]['candidates'].pop()
        elif damage=='false_selection':altered['selected']=True
        else:altered['cases'][0]['candidates'][0]['compatibility_sha256']='0'*64
        try:audit(altered)
        except (ValueError,KeyError):rejected+=1
        else:raise ValueError('Damaged statutory exact proof accepted')
    result['isolated_negative_rejections']=rejected
    print(json.dumps(result,sort_keys=True))
