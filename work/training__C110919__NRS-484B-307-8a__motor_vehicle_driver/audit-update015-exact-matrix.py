"""Independently bind right-turn exact receipts to raw stop and yield sources."""
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


def rows(text):return [json.loads(line) for line in text.splitlines() if line.strip()]


def audit(index=None):
    index=index or json.loads((HERE/'update015-proof-index.json').read_text())
    require(index['selected'] is False and index['physical_acceptance_claimed'] is False and
            index['compatibility_passed']==index['process_saved_passed']==8 and
            len(index['cases'])==2,'Right-turn exact matrix incomplete')
    manifest_path=HERE/'draft-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    require(manifest['runtime_manifest_sha256']==sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Runtime source changed')
    by_case={case['case_id']:case for case in manifest['cases']}
    stops={};yield_zone={};joined=0;pair=[]
    for suffix,case_row in zip(('reference','contrast'),index['cases']):
        case_id=HERE.name+'__'+suffix
        require(case_row['case_id']==case_id and case_id in by_case,'Right-turn case differs')
        construction=by_case[case_id]
        candidates=[{'id':'primary','construction':construction['construction'],
                     'construction_sha256':construction['construction_sha256']}]+construction['candidates']
        require([row['id'] for row in candidates]==list(CANDIDATES) and
                [row['candidate_id'] for row in case_row['candidates']]==list(CANDIDATES),
                'Right-turn candidate inventory differs')
        require(len({row['construction_sha256'] for row in candidates})==4 and
                len({(row['trigger']['source'],row['trigger']['metric'],
                     row['trigger']['failure_condition']) for row in candidates[1:]})==3,
                'Right-turn fallback constructions or triggers duplicate')
        spec_path=HERE/f'update015-{suffix}-diagnostic.json'
        recipe_path=HERE/f'update015-{suffix}-recipe.json'
        recipe=json.loads(recipe_path.read_text())
        require(recipe['sources'][0]['sha256']==sha(spec_path),'Right-turn recipe changed')
        spec=json.loads(spec_path.read_text())
        require([v['path'] for v in spec['videos']]==[name+'.mkv' for name in CAMERAS] and
                all(v['frames']==480 for v in spec['videos']),
                'Right-turn source camera recipe differs')
        samples=rows(spec['files']['native_samples.jsonl'])
        frames=rows(spec['files']['video_frames.jsonl'])
        body=rows(spec['files']['body_history.jsonl'])
        trace=rows(spec['files']['trace.jsonl'])
        evidence=rows(spec['files']['capture/evidence.jsonl'])
        native=rows(spec['files']['capture/native/frames.jsonl'])
        geometry=json.loads(spec['files']['road_geometry.json'])
        require(all(len(x)==480 for x in (samples,frames,body,trace,evidence,native)) and
                geometry['stop_line_y_m']==-14.0 and geometry['signal_actor_id']==601,
                'Right-turn raw source inventory differs')
        crossing=None;previous=None;halt=[]
        for i,(s,f,b,t,e,n) in enumerate(zip(samples,frames,body,trace,evidence,native)):
            require(f['video_frame']==i and
                    s['native_frame']==f['native_frame']==b['frame']==t['frame']==e['original_frame']==n['frame'] and
                    abs(s['time_s']-f['time_s'])<1e-6 and
                    abs(s['time_s']-t['time_s'])<1e-6 and
                    abs(s['time_s']-e['recording_time_s'])<1e-6 and
                    s['speed_mps']==t['speed_mps']==e['ego']['speed_mps'] and
                    s['speed_provenance']==t['speed_provenance']==e['ego']['speed_provenance']=='synthetic_native_sample' and
                    s['signal_state_observed']=='Red',
                    'Right-turn raw join, signal or speed provenance differs')
            front=max(p[1] for p in s['native_body_xy_m'])
            if crossing is None and previous is not None and previous< -14<=front:
                crossing=i
            previous=front
            if s['speed_mps']<=.05 and front< -14:halt.append(i)
            joined+=1
        require(crossing is not None,'No sampled stop-line crossing')
        longest=0;span=0;prior=-2
        for i in (x for x in halt if x<crossing):
            span=span+1 if i==prior+1 else 1
            longest=max(longest,span);prior=i
        stops[suffix]={'crossing':crossing,'stationary_pre_crossing_frames':longest}
        last_occupied=max(i for i,s in enumerate(samples) if s['walker_conflict_occupied'] is True)
        first_destination_zone=next(i for i,s in enumerate(samples)
                                    if s['native_center_xy_m'][0]>=8 and
                                    s['native_center_xy_m'][1]>-7)
        yield_zone[suffix]={'last_walker_conflict_frame':last_occupied,
                            'first_destination_zone_frame':first_destination_zone,
                            'sampled_clearance_s':round((first_destination_zone-last_occupied)/20,3)}
        pair.append((samples,geometry,spec['videos'],evidence))
        for expected,proof in zip(candidates,case_row['candidates']):
            folder=HERE/'update015-exact-proofs'/suffix/expected['id']
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
                    'Right-turn exact source binding differs')
            measured=compat['measurement_examples']['right_turn_stop']['value']
            yield_value=compat['measurement_examples']['right_turn_yield']['value']
            require(compat['passed'] is True and compat['negative_removed']=='road_geometry.json' and
                    compat['fixture_manifest']['diagnostic-input.json']==sha(spec_path) and
                    measured['stationary_pre_crossing_frames']==longest and
                    measured['first_front_crossing_frame']==crossing and
                    measured['halt_before_nearest_boundary'] is (longest>=10) and
                    compat['measurement_examples']['steady_red_activation']['value']['steady_red_frames']==480 and
                    yield_value['turn_entry_frame']==first_destination_zone and
                    yield_value['last_walker_conflict_frame']==last_occupied and
                    yield_value['sampled_clearance_s']==yield_zone[suffix]['sampled_clearance_s'] and
                    yield_value['sampled_clearance_s']>0 and
                    saved['passed'] is True and saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames']==480 and
                    saved['final_video_checks']['passed'] is True and
                    saved['final_video_checks']['frames']==480 and
                    saved['missing_evidence'] is False and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Right-turn exact measurement or saved receipt differs')
    require(stops['reference']['stationary_pre_crossing_frames']==30 and
            stops['contrast']['stationary_pre_crossing_frames']==0 and
            pair[0][1]==pair[1][1] and pair[0][2]==pair[1][2] and
            all(a['signal_state_observed']==b['signal_state_observed'] and
                a['walker_conflict_occupied']==b['walker_conflict_occupied']
                for a,b in zip(pair[0][0],pair[1][0])) and
            all(a['world']['weather']==b['world']['weather']
                for a,b in zip(pair[0][3],pair[1][3])),
            'Right-turn controlled pair differs outside stop behavior')
    return {'raw_frame_joins_checked':joined,'exact_compatibility_passed':8,
            'exact_process_saved_passed':8,'stops':stops,
            'destination_conflict_zone':yield_zone,'selected':False}


if __name__=='__main__':
    result=audit()
    original=json.loads((HERE/'update015-proof-index.json').read_text())
    rejected=0
    for damage in ('missing_candidate','false_selection','wrong_receipt'):
        altered=copy.deepcopy(original)
        if damage=='missing_candidate':altered['cases'][0]['candidates'].pop()
        elif damage=='false_selection':altered['selected']=True
        else:altered['cases'][0]['candidates'][0]['compatibility_sha256']='0'*64
        try:audit(altered)
        except (ValueError,KeyError):rejected+=1
        else:raise ValueError('Damaged right-turn exact proof accepted')
    result['isolated_negative_rejections']=rejected
    print(json.dumps(result,sort_keys=True))
