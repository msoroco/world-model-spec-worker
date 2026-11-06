"""Two controlled 480-frame source-bound CPU passing diagnostics and negatives."""
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

OUT=ROOT/'.runtime-work/c102372-passing'


def write_case(passing):
    root=OUT/('pass' if passing else 'hold')
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    (root/'road.xodr').write_text(open_drive()+'\n')
    context={'source_kind':'synthetic_cpu_fixture','same_direction_lane_count':1,
             'passing_attempt':passing,'opposing_traffic_source':'synthetic_empty'}
    (root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
    rows=[]
    for frame in range(480):
        t=frame/20
        lead_x=248+8*t
        ego_x=210+(12 if passing else 8)*t
        if passing:
            if t<2:y=-2
            elif t<4:y=-2+2*(t-2)
            elif t<16:y=2
            elif t<18:y=2-2*(t-16)
            else:y=-2
        else:y=-2
        rows.append({'native_frame':frame,'time_s':t,'opposing_lane_actors':[],
                     'ego':{'actor_class':'truck_or_combination','road_id':1,
                            'lane_id':-1 if y<0 else 1,'speed_mps':12 if passing else 8,
                            'body_xy_m':body(ego_x,y)},
                     'lead':{'actor_class':'truck_or_combination','road_id':1,
                             'lane_id':-1,'speed_mps':8,'body_xy_m':body(lead_x)}})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    resign(root)
    return root


def resign(root):
    (root/'source-manifest.json').write_text(json.dumps({'format':'c102372-passing-source-v1',
        'sha256':{name:sha(root/name) for name in NAMES}},sort_keys=True)+'\n')


def reject(root,expected):
    try:measure(root)
    except ValueError as error:
        if expected not in str(error):raise
    else:raise AssertionError('Invalid passing source accepted')


def main():
    roots={key:write_case(key=='pass') for key in ('hold','pass')}
    values={key:measure(root) for key,root in roots.items()}
    if values['hold']['passing_sequence_observed'] or not values['pass']['passing_sequence_observed']:
        raise AssertionError('Controlled passing pair differs')
    if values['hold']['opposing_lane_frames'] or values['pass']['opposing_lane_frames']<200:
        raise AssertionError('Controlled passing lane exposure differs')
    if any(value['legal_verdict_claimed'] or value['physical_opposing_clearance_verified'] for value in values.values()):
        raise AssertionError('Synthetic physical/legal verdict claimed')
    root=roots['pass']
    samples=root/'native_samples.jsonl';original=samples.read_bytes()
    samples.write_bytes(original+b' ');reject(root,'Passing source missing or changed')
    samples.write_bytes(original)
    rows=[json.loads(line) for line in original.splitlines()]
    rows[100]['opposing_lane_actors']=[{'id':'oncoming'}]
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
    reject(root,'Opposing-lane source is not clear')
    rows=[json.loads(line) for line in original.splitlines()]
    rows[200]['ego']['body_xy_m']=body(lead_x:=rows[200]['lead']['body_xy_m'][0][0]+6,-2)
    rows[200]['ego']['lane_id']=-1
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
    reject(root,'Passing truck bodies collide')
    rows=[json.loads(line) for line in original.splitlines()]
    rows=rows[:-1]
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
    reject(root,'Full passing frame source absent')
    samples.write_bytes(original);resign(root)
    context=root/'following_context.json';original_context=context.read_bytes()
    data=json.loads(original_context);data['passing_attempt']=False
    context.write_text(json.dumps(data)+'\n');resign(root)
    reject(root,'Passing sequence differs from context')
    context.write_bytes(original_context);resign(root)
    if measure(root)!=values['pass']:raise AssertionError('Restored passing source differs')
    return {'passed':True,'cases':{key:{'passing':value['passing_sequence_observed'],
           'opposing_lane_frames':value['opposing_lane_frames'],
           'minimum_clearance_m':value['minimum_body_clearance_m']} for key,value in values.items()},
           'negative_rejections':5,'physical_or_legal_verdict_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
