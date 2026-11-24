"""Source-bound 600-frame follow/abreast diagnostics and adversarial checks."""
import json
import os
from pathlib import Path
import tempfile
from measure_emergency import AID,measure


def fixture(root,abreast):
    root.mkdir();ctx={'assignment_id':AID,'review_kind':'synthetic_diagnostic','reviewer':'synthetic fixture',
        'ego_actor_id':1,'emergency_actor_id':2,'emergency_vehicle_authorized':True,
        'qualifying_flash_equipment_reviewed':True,'officer_directed_otherwise':False}
    for key in ('ego_driver_source','ego_vehicle_source','emergency_authorization_source',
        'qualifying_flash_equipment_source','flashing_light_visual_source',
        'lane_boundary_source','officer_direction_review_source'):
        ctx[key]='synthetic-fixture:'+key
    (root/'emergency_context.json').write_text(json.dumps(ctx)+'\n')
    with (root/'video_frames.jsonl').open('w') as f,(root/'vehicle_poses.jsonl').open('w') as p:
        for i in range(600):
            n=100+i;t=i*.05;x=i*.2
            f.write(json.dumps({'video_frame':i,'native_frame':n,'time_s':t})+'\n')
            em={'actor_id':2,'x_m':x,'y_m':0,'heading_rad':0,'speed_mps':4,
                'half_length_m':2.5,'half_width_m':1,'flashing_light_phase_on':(i//10)%2==0}
            gap=-20+min(i*.05,19) if abreast else -20
            ego={'actor_id':1,'x_m':x+gap,'y_m':3.5,
                 'heading_rad':0,'speed_mps':5 if abreast and i<380 else 4,
                 'half_length_m':2.5,'half_width_m':1}
            p.write(json.dumps({'video_frame':i,'native_frame':n,'source_kind':'synthetic_native_sample',
                                'ego':ego,'emergency':em})+'\n')


def reject(root):
    try:measure(root)
    except ValueError:return
    raise AssertionError('Statutory source defect accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='emergency-proof-',dir=os.environ['TMPDIR']) as temp:
        root=Path(temp);a=root/'behind';b=root/'abreast';fixture(a,False);fixture(b,True)
        follow,beside=measure(a),measure(b)
        assert all(r['longitudinal_overlap_length_m']==0 for r in follow['per_frame_geometry'])
        assert beside['per_frame_geometry'][0]['longitudinal_overlap_length_m']==0
        assert beside['per_frame_geometry'][-1]['longitudinal_overlap_length_m']>0
        assert follow['relative_order_crossings']==beside['relative_order_crossings']==0
        c=json.loads((a/'emergency_context.json').read_text());c['emergency_vehicle_authorized']=False
        (a/'emergency_context.json').write_text(json.dumps(c)+'\n');reject(a)
        lines=(b/'vehicle_poses.jsonl').read_text().splitlines();r=json.loads(lines[200]);r['emergency']['flashing_light_phase_on']=None;lines[200]=json.dumps(r)
        (b/'vehicle_poses.jsonl').write_text('\n'.join(lines)+'\n');reject(b)
        c['emergency_vehicle_authorized']=True;c['officer_directed_otherwise']='unknown'
        (a/'emergency_context.json').write_text(json.dumps(c)+'\n');reject(a)
        print(json.dumps({'follow_overlap_frames':0,
            'beside_overlap_frames':sum(r['longitudinal_overlap_length_m']>0 for r in beside['per_frame_geometry']),
            'overtake_crossings':0,'negative_source_checks':3,'legal_result':None},sort_keys=True))


if __name__=='__main__':main()
