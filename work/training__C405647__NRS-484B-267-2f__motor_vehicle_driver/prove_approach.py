"""Synthetic source-shape diagnostics; never Native or legal proof."""
import json
import os
from pathlib import Path
import tempfile
from native.measure_approach import AID,measure


def fixture(root,slow):
    root.mkdir()
    c={'assignment_id':AID,'review_kind':'synthetic_diagnostic','reviewer':'synthetic fixture',
       'ego_actor_id':1,'emergency_actor_id':2,'emergency_vehicle_authorized':True,
       'qualifying_flash_equipment_reviewed':True,'officer_directed_otherwise':False}
    for k in ('ego_driver_source','emergency_authorization_source','qualifying_flash_equipment_source',
              'flashing_light_visual_source','lane_boundary_source','visibility_review_source',
              'officer_direction_review_source'):c[k]='synthetic-fixture:'+k
    (root/'emergency_context.json').write_text(json.dumps(c)+'\n')
    ego_x=-75.0;em_x=-15.0
    with (root/'video_frames.jsonl').open('w') as frames,(root/'vehicle_poses.jsonl').open('w') as poses:
        for i in range(600):
            es=1 if slow and i>=100 else 3
            ms=2 if i>=100 else 0
            ego_x+=es*.05;em_x-=ms*.05
            n=1000+i
            frames.write(json.dumps({'video_frame':i,'native_frame':n,'time_s':i*.05})+'\n')
            e={'actor_id':1,'x_m':ego_x,'y_m':-1.75,'heading_rad':0,
               'velocity_x_mps':es,'velocity_y_mps':0,'speed_mps':es,
               'half_length_m':2,'half_width_m':1}
            m={'actor_id':2,'x_m':em_x,'y_m':1.75,'heading_rad':3.141592653589793,
               'velocity_x_mps':-ms,'velocity_y_mps':0,'speed_mps':ms,
               'half_length_m':2,'half_width_m':1,'special1_light_on':(i//10)%2==0}
            poses.write(json.dumps({'video_frame':i,'native_frame':n,'source_kind':'synthetic_native_sample',
                                    'ego':e,'emergency':m})+'\n')

def reject(root,expected):
    try:measure(root)
    except ValueError as exc:
        if expected not in str(exc):raise
    else:raise AssertionError('Adversarial source defect accepted: '+expected)

def main():
    with tempfile.TemporaryDirectory(prefix='c405647-267-2f-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp);a=root/'slow';b=root/'continue';fixture(a,True);fixture(b,False)
        x,y=measure(a),measure(b)
        assert x['initial_subject_approach_m']>10 and y['initial_subject_approach_m']>10
        assert x['subsequent_emergency_approach_m']>10 and y['subsequent_emergency_approach_m']>20
        assert x['ego_speed_after_mps']==1 and y['ego_speed_after_mps']==3
        c=json.loads((a/'emergency_context.json').read_text());c['emergency_vehicle_authorized']=False
        (a/'emergency_context.json').write_text(json.dumps(c)+'\n');reject(a,'authorization')
        c['emergency_vehicle_authorized']=True;c['officer_directed_otherwise']='unknown'
        (a/'emergency_context.json').write_text(json.dumps(c)+'\n');reject(a,'Officer direction')
        lines=(b/'vehicle_poses.jsonl').read_text().splitlines();r=json.loads(lines[150]);r['emergency']['special1_light_on']=None;lines[150]=json.dumps(r)
        (b/'vehicle_poses.jsonl').write_text('\n'.join(lines)+'\n');reject(b,'light state')
        print(json.dumps({'paired_600_frame_source_join':True,'initial_subject_approach_m':x['initial_subject_approach_m'],
                          'subsequent_emergency_approach_m':x['subsequent_emergency_approach_m'],
                          'ego_speed_after_mps':[x['ego_speed_after_mps'],y['ego_speed_after_mps']],
                          'negative_source_checks':3,'native_executed':False,'legal_result':None},sort_keys=True))
if __name__=='__main__':main()
