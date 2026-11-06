"""Source-measured CPU fallback thresholds for two conditions Native plans."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-conditions-engineering'
sys.path.insert(0,str(HERE/'native'))
from geometry import body,open_drive
from measure_gap import sha
from conditions_engineering import ASSIGNMENT,CASES,CANDIDATES,check,construction
from conditions_qualifier import NAMES,measure
from conditions_trigger import extract,decide


def write_case(case,candidate='primary',kind='baseline'):
    folder=case+'-'+(candidate if kind=='baseline' else kind)
    root=OUT/folder
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    (root/'road.xodr').write_text(open_drive()+'\n')
    event=case=='conditions_lead_brake'
    (root/'following_context.json').write_text(json.dumps({
        'case_id':ASSIGNMENT+'__'+case,'source_kind':'synthetic_cpu_fixture',
        'same_direction_lane_count':1,
        'event':'lead_brake_with_obstacle' if event else 'steady'},sort_keys=True)+'\n')
    k=construction(case,candidate)['knobs'];rows=[]
    lead_x=187.+k['initial_horizontal_gap_m']-155.;ego_x=20.
    for frame in range(480):
        t=frame/20
        if event:
            if t<=8:lead_x=187+k['initial_horizontal_gap_m']-155+8*t;lead_speed=8.
            elif t<10:
                u=t-8;lead_x=251+k['initial_horizontal_gap_m']-155+8*u-2*u*u
                lead_speed=8-4*u
            else:lead_x=259+k['initial_horizontal_gap_m']-155;lead_speed=0.
            stop=k['ego_brake_stop_s']
            if t<=9:ego_x=20+8*t;ego_speed=8.
            elif t<stop:
                u=t-9;duration=stop-9
                ego_x=92+8*u-4*u*u/duration;ego_speed=8-8*u/duration
            else:ego_x=92+4*(stop-9);ego_speed=0.
        else:
            ego_speed=k['ego_speed_mps'];lead_speed=k['lead_speed_mps']
            if kind=='gap_compress' and 200<=frame<220:lead_speed=7.
            if kind=='speed_mismatch' and 200<=frame<220:lead_speed=6.
            if frame:
                ego_x+=ego_speed/20;lead_x+=lead_speed/20
        obstacle_x=k['obstacle_x_m']
        rows.append({'native_frame':frame,'time_s':t,
            'ego':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                   'speed_mps':ego_speed,'body_xy_m':body(ego_x)},
            'lead':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                    'speed_mps':lead_speed,'body_xy_m':body(lead_x)},
            'obstacle':{'actor_class':'stopped_vehicle','lane_id':-1,
                        'body_xy_m':body(obstacle_x)} if event else None})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    (root/'source-manifest.json').write_text(json.dumps({
        'format':'c102372-conditions-source-v1',
        'sha256':{name:sha(root/name) for name in NAMES}},sort_keys=True)+'\n')
    return root


def reject(call,contains):
    try:call()
    except ValueError as error:
        if contains not in str(error):raise
    else:raise AssertionError('Invalid conditions source/trigger accepted')


def main():
    check();values={}
    for case in CASES:
        values[case]={}
        for candidate in CANDIDATES:
            source=write_case(case,candidate);measured=measure(source);value=extract(source,case)
            if measured['lead_braking_gap_compression_observed']!=(case=='conditions_lead_brake'):
                raise AssertionError('Conditions candidate lost controlled event')
            values[case][candidate]=value
    steady=CASES[0];event=CASES[1]
    positives={
        (steady,'fallback1'):values[steady]['primary'],
        (steady,'fallback2'):extract(write_case(steady,kind='gap_compress'),steady),
        (steady,'fallback3'):extract(write_case(steady,kind='speed_mismatch'),steady),
        (event,'fallback1'):values[event]['primary'],
        (event,'fallback2'):values[event]['primary'],
        (event,'fallback3'):values[event]['primary'],
    }
    negatives={
        (steady,'fallback1'):values[steady]['fallback1'],
        (steady,'fallback2'):values[steady]['primary'],
        (steady,'fallback3'):values[steady]['primary'],
        (event,'fallback1'):values[event]['fallback1'],
        (event,'fallback2'):values[event]['fallback2'],
        (event,'fallback3'):values[event]['fallback3'],
    }
    for (case,candidate),positive in positives.items():
        if not decide(positive,case,candidate,diagnostic=True) or \
           decide(negatives[case,candidate],case,candidate,diagnostic=True):
            raise AssertionError('Conditions measured threshold did not discriminate '+case+'/'+candidate)
    reject(lambda:decide(values[steady]['primary'],steady,'fallback1'),
           'Original Native conditions source required')
    changed=dict(values[event]['primary']);changed['metrics']={**changed['metrics'],
        'minimum_surface_gap_m':999.}
    reject(lambda:decide(changed,event,'fallback1',diagnostic=True),
           'metric identity or digest')
    source=OUT/(event+'-primary');samples=source/'native_samples.jsonl';original=samples.read_bytes()
    samples.write_bytes(original+b' ')
    reject(lambda:extract(source,event),'Conditions source missing or changed')
    samples.write_bytes(original)
    return {'passed':True,'case_count':2,'candidate_count':8,'trigger_count':6,
            'baseline_metrics':{case:{name:value['metrics'] for name,value in group.items()}
                                for case,group in values.items()},
            'positive_metrics':{case+'/'+name:value['metrics'] for (case,name),value in positives.items()},
            'negative_rejections':3,'synthetic_cpu_only':True,
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
