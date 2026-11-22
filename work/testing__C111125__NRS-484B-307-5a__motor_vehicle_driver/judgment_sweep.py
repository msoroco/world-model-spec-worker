"""CPU kinematic probes for exhibition-time occupancy; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from runner import authored_arrow_state, control_step, load_scene, participant_motion

ROOT=Path(__file__).resolve().parent
PROFILES=(('before_entry',1.0,False),('during_occupancy',5.0,True),
          ('after_clearance',12.0,False))


def rectangle(left,bottom,right,top):
    return [[left,bottom,0],[right,bottom,0],[right,top,0],[left,top,0]]


def participants(scene,elapsed_s):
    """Source-shaped nominal footprints from the authored spawn and motion policy."""
    policy=participant_motion(scene,elapsed_s)
    vehicle_y=-12+policy['vehicle_velocity_xyz_mps'][1]*elapsed_s
    walker_y=-9+policy['pedestrian_speed_mps']*elapsed_s
    return [{'id':17,'role':'vehicle',
             'body_vertices_m':rectangle(-1,vehicle_y-2,1,vehicle_y+2),
             'lawfully_present':True,
             'lawful_presence_source':'synthetic-phase-fixture-only'},
            {'id':18,'role':'pedestrian',
             'body_vertices_m':rectangle(9,walker_y-.3,10,walker_y+.3),
             'lawfully_present':True,
             'lawful_presence_source':'synthetic-phase-fixture-only'}]


def signal(frame):
    return {'frame':frame,'facing_head_id':7,
            'aspect':{'source_verified':True,'source_ref':'synthetic-arrow-fixture-only',
                      'head_id':7,'observed_frame':frame,
                      'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}}


def run():
    base=load_scene()
    if base['participant_occupancy_setup']!='clear':
        raise ValueError('expected exact base scene')
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                   for name in ('scene.json','runner.py')}
    results=[]
    for label,exhibition,expected_hold in PROFILES:
        scene={**base,'participant_occupancy_setup':'lawfully_present',
               'arrow_exhibition_after_s':exhibition}
        frame=round(exhibition*scene['capture_rate_hz'])
        if authored_arrow_state(scene,exhibition-1/scene['capture_rate_hz'])!='Red' or \
           authored_arrow_state(scene,exhibition)!='Green':
            raise ValueError('arrow schedule does not exhibit at selected sweep frame')
        observed=participants(scene,exhibition)
        ego=rectangle(-12,-.5,-11,.5)
        decision=control_step(scene,signal(frame),observed,ego)
        hold=decision['reason']=='yield_hold'
        if hold!=expected_hold or (hold and set(decision['occupied_by'])!={17,18}):
            raise ValueError('nominal exhibition occupancy differs from sweep plan: '+label)
        row={'profile':label,'case_id':base['case_id'].rsplit('__',1)[0]+'__yield_straight',
             'exhibition_time_s':exhibition,'exhibition_frame':frame,
             'nominal_participants':observed,'controller_reason':decision['reason'],
             'hold_at_stop_line':hold,'legal_verdict':None}
        if hold:
            clear_frame=round(12*scene['capture_rate_hz'])
            cleared=control_step(scene,signal(clear_frame),participants(scene,12),ego,
                                 first_arrow_frame=frame,
                                 exhibition_occupants=decision['exhibition_occupants'])
            if cleared['reason']!='straight_clear':
                raise ValueError('nominal clearance did not release hold')
            row['nominal_clearance_frame']=clear_frame
        results.append(row)
    return {'format':'c111125-judgment-kinematic-sweep-v1',
            'source_sha256':source_hashes,'scope':'synthetic kinematic construction probe only',
            'source_requirements':['original sole-arrow frame and head asset',
                                   'original participant bodies and phase entry',
                                   'reviewed intersection and adjacent crosswalk geometry',
                                   'original ego body and camera pixels'],
            'profiles':results,'physical_result':None,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    proof=run();args.output.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'profiles':len(proof['profiles']),
                      'holds':[row['hold_at_stop_line'] for row in proof['profiles']],
                      'physical_result':None}))


if __name__=='__main__':main()
