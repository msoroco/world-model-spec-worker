"""Source-measured CPU positives, negatives, and controlled no-passing pair."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import body,open_drive
from measure_gap import sha
from passing_carveout import NAMES,measure
from passing_hold_engineering import ASSIGNMENT,CASE,CANDIDATES,check,construction
from passing_hold_trigger import extract,decide

OUT=ROOT/'.runtime-work/c102372-passing-hold-engineering'


def write_case(candidate,kind='baseline'):
    root=OUT/(candidate if kind=='baseline' else kind)
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    (root/'road.xodr').write_text(open_drive()+'\n')
    (root/'following_context.json').write_text(json.dumps({
        'case_id':ASSIGNMENT+'__'+CASE,'source_kind':'synthetic_cpu_fixture',
        'same_direction_lane_count':1,'passing_attempt':False,
        'opposing_traffic_source':'synthetic_empty'},sort_keys=True)+'\n')
    k=construction(candidate)['knobs'];rows=[];lead_x=248.
    ego_x=210. if kind!='short_gap' else 218.
    for frame in range(480):
        t=frame/20
        if kind=='speed_mismatch' and 200<=frame<220:lead_speed=6.
        else:lead_speed=k['lead_speed_mps']
        if frame:
            lead_x+=lead_speed/20
            ego_x+=k['ego_speed_mps']/20
        y=-1.6 if kind=='lane_drift' and 200<=frame<220 else -2.
        rows.append({'native_frame':frame,'time_s':t,'opposing_lane_actors':[],
            'ego':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                   'speed_mps':k['ego_speed_mps'],'body_xy_m':body(ego_x,y)},
            'lead':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                    'speed_mps':lead_speed,'body_xy_m':body(lead_x,-2.)}})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    (root/'source-manifest.json').write_text(json.dumps({
        'format':'c102372-passing-source-v1',
        'sha256':{name:sha(root/name) for name in NAMES}},sort_keys=True)+'\n')
    return root


def reject(call,contains):
    try:call()
    except ValueError as error:
        if contains not in str(error):raise
    else:raise AssertionError('Invalid hold source or trigger accepted')


def main():
    check();values={}
    for candidate in CANDIDATES:
        source=write_case(candidate);measured=measure(source);value=extract(source)
        if measured['passing_sequence_observed'] or measured['opposing_lane_frames'] or \
           value['passing_sequence_observed'] or measured['minimum_body_clearance_m']<=20:
            raise AssertionError('Controlled hold source passed or lost clearance')
        values[candidate]=value
    positives={
        'fallback1':extract(write_case('primary','short_gap')),
        'fallback2':extract(write_case('primary','speed_mismatch')),
        'fallback3':extract(write_case('primary','lane_drift')),
    }
    for candidate,positive in positives.items():
        if not decide(positive,candidate,diagnostic=True) or \
           decide(values['primary'],candidate,diagnostic=True):
            raise AssertionError('Source-measured hold trigger did not discriminate '+candidate)
    reject(lambda:decide(values['primary'],'fallback1'),
           'Original Native hold source required')
    altered=dict(positives['fallback1']);altered['metrics']={**altered['metrics'],
        'minimum_body_clearance_m':99.}
    reject(lambda:decide(altered,'fallback1',diagnostic=True),'metric identity or digest')
    source=OUT/'short_gap';samples=source/'native_samples.jsonl';original=samples.read_bytes()
    samples.write_bytes(original+b' ')
    reject(lambda:extract(source),'Passing source missing or changed')
    samples.write_bytes(original)
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,
            'candidate_count':4,'baseline_metrics':{name:value['metrics'] for name,value in values.items()},
            'positive_metrics':{name:value['metrics'] for name,value in positives.items()},
            'negative_rejections':3,'synthetic_cpu_only':True,
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
