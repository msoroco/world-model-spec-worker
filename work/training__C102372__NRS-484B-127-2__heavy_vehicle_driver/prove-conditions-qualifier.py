"""Source-hashed 480-frame lead-braking controlled pair and adversarial negatives."""
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import body,open_drive
from measure_gap import sha
from conditions_qualifier import measure,NAMES

OUT=ROOT/'.runtime-work/c102372-conditions'


def write_case(event):
    root=OUT/('lead_brake' if event else 'steady')
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    (root/'road.xodr').write_text(open_drive()+'\n')
    context={'source_kind':'synthetic_cpu_fixture','same_direction_lane_count':1,
             'event':'lead_brake_with_obstacle' if event else 'steady'}
    (root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
    rows=[]
    for frame in range(480):
        t=frame/20
        if event:
            if t<=8:lead_x,lead_speed=187+8*t,8
            elif t<10:
                u=t-8;lead_x,lead_speed=251+8*u-2*u*u,8-4*u
            else:lead_x,lead_speed=259,0
            if t<=9:ego_x,ego_speed=20+8*t,8
            elif t<13:
                u=t-9;ego_x,ego_speed=92+8*u-u*u,8-2*u
            else:ego_x,ego_speed=108,0
        else:
            lead_x,lead_speed=187+8*t,8
            ego_x,ego_speed=20+8*t,8
        rows.append({'native_frame':frame,'time_s':t,
                     'ego':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                            'speed_mps':ego_speed,'body_xy_m':body(ego_x)},
                     'lead':{'actor_class':'truck_or_combination','road_id':1,'lane_id':-1,
                             'speed_mps':lead_speed,'body_xy_m':body(lead_x)},
                     'obstacle':{'actor_class':'stopped_vehicle','lane_id':-1,
                                 'body_xy_m':body(285)} if event else None})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    resign(root)
    return root


def resign(root):
    (root/'source-manifest.json').write_text(json.dumps({'format':'c102372-conditions-source-v1',
        'sha256':{name:sha(root/name) for name in NAMES}},sort_keys=True)+'\n')


def reject(root,expected):
    try:measure(root)
    except ValueError as error:
        if expected not in str(error):raise
    else:raise AssertionError('Invalid conditions source accepted')


def main():
    roots={key:write_case(key=='lead_brake') for key in ('steady','lead_brake')}
    values={key:measure(root) for key,root in roots.items()}
    if values['steady']['lead_braking_gap_compression_observed'] or \
            not values['lead_brake']['lead_braking_gap_compression_observed']:
        raise AssertionError('Controlled conditions pair differs')
    if any(value['legal_verdict_claimed'] or value['physical_conditions_permit_verified'] for value in values.values()):
        raise AssertionError('Physical or legal verdict claimed')
    root=roots['lead_brake'];samples=root/'native_samples.jsonl';original=samples.read_bytes()
    samples.write_bytes(original+b' ');reject(root,'Conditions source missing or changed')
    samples.write_bytes(original)
    rows=[json.loads(line) for line in original.splitlines()]
    rows[0]['obstacle']=None
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
    reject(root,'Conditions event differs from measured source')
    rows=[json.loads(line) for line in original.splitlines()]
    rows[200]['obstacle']['body_xy_m']=body(262)
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
    reject(root,'Conditions lead/obstacle collision')
    rows=[json.loads(line) for line in original.splitlines()]
    samples.write_text(''.join(json.dumps(row)+'\n' for row in rows[:-1]));resign(root)
    reject(root,'Full conditions frame source absent')
    samples.write_bytes(original);resign(root)
    context=root/'following_context.json';original_context=context.read_bytes()
    data=json.loads(original_context);data['event']='steady'
    context.write_text(json.dumps(data)+'\n');resign(root)
    reject(root,'Conditions event differs from measured source')
    context.write_bytes(original_context);resign(root)
    if measure(root)!=values['lead_brake']:raise AssertionError('Restored source differs')
    return {'passed':True,'cases':{key:{'event':value['lead_braking_gap_compression_observed'],
            'initial_gap_m':value['initial_horizontal_gap_m'],
            'minimum_gap_m':value['minimum_horizontal_gap_m'],
            'surface_compression_m':value['surface_gap_compression_m'],
            'minimum_surface_gap_m':value['minimum_surface_gap_m']} for key,value in values.items()},
            'negative_rejections':5,'physical_or_legal_verdict_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
