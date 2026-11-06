"""Synthetic 480-frame measured triggers for four passing Native requests."""
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
from passing_carveout import measure,NAMES
from passing_engineering import ASSIGNMENT,CASE,CANDIDATES,check,request
from passing_trigger import extract,decide

OUT=ROOT/'.runtime-work/c102372-passing-engineering'


def write_case(name,speed=None,label=None):
    root=OUT/(label or name)
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    (root/'road.xodr').write_text(open_drive()+'\n')
    (root/'following_context.json').write_text(json.dumps({
        'case_id':ASSIGNMENT+'__'+CASE,
        'source_kind':'synthetic_cpu_fixture','same_direction_lane_count':1,
        'passing_attempt':True,'opposing_traffic_source':'synthetic_empty'},sort_keys=True)+'\n')
    rows=[]
    for frame in range(480):
        value=request(name,frame);t=value['time_s'];ego_speed=speed or value['ego_speed_mps']
        x=210+ego_speed*t;y=value['ego_target_y_m'];lead_x=248+8*t
        rows.append({'native_frame':frame,'time_s':t,'opposing_lane_actors':[],
            'ego':{'actor_class':'truck_or_combination','road_id':1,
                   'lane_id':value['intended_lane_id'],'speed_mps':ego_speed,
                   'body_xy_m':body(x,y)},
            'lead':{'actor_class':'truck_or_combination','road_id':1,
                    'lane_id':-1,'speed_mps':8,'body_xy_m':body(lead_x)}})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n'
                                                for row in rows))
    (root/'source-manifest.json').write_text(json.dumps({
        'format':'c102372-passing-source-v1','sha256':{key:sha(root/key)
        for key in NAMES}},sort_keys=True)+'\n')
    return root


def reject(call,expected):
    try:call()
    except ValueError as error:
        if expected not in str(error):raise
    else:raise AssertionError('Invalid passing trigger/source accepted')


def main():
    check();values={}
    for name in CANDIDATES:
        source=write_case(name);measured=measure(source);result=extract(source)
        if not measured['passing_sequence_observed'] or result['metrics']!={
            key:measured[key] for key in result['metrics']}:
            raise AssertionError('Passing request did not produce a measured sequence')
        values[name]=result
    under=extract(write_case('primary',speed=11.5,label='underperforming'))
    if not decide(under,'fallback1',diagnostic=True) or \
       decide(values['primary'],'fallback1',diagnostic=True):
        raise AssertionError('Final-pass margin threshold not crossed')
    if not decide(values['primary'],'fallback2',diagnostic=True) or \
       decide(values['fallback2'],'fallback2',diagnostic=True):
        raise AssertionError('Truck-body clearance threshold not crossed')
    if not decide(values['primary'],'fallback3',diagnostic=True) or \
       decide(values['fallback3'],'fallback3',diagnostic=True):
        raise AssertionError('Opposing-lane exposure threshold not crossed')
    reject(lambda:decide(values['primary'],'fallback2'),
           'Original Native passing source required')
    changed=dict(values['primary']);changed['metrics']={**changed['metrics'],
        'minimum_body_clearance_m':9.}
    reject(lambda:decide(changed,'fallback2',diagnostic=True),'metric identity or digest')
    source=OUT/'fallback2';samples=source/'native_samples.jsonl'
    original=samples.read_bytes();samples.write_bytes(original+b' ')
    reject(lambda:extract(source),'Passing source missing or changed')
    samples.write_bytes(original)
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,'candidate_count':4,
        'metrics':{name:value['metrics'] for name,value in values.items()},
        'underperforming_final_offset_m':under['metrics']['final_center_offset_m'],
        'negative_rejections':3,'synthetic_cpu_only':True,
        'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
