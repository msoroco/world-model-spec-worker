"""Build the separately controlled, visibly preparing driver-hand-signal case."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
CASE=AID+'__preparing_hand_signal'
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('drv.responding_emergency','rel.same_direction','rel.longitudinal_overlap',
          'drv.overtaking','rel.ahead_behind_in_lane','kin.velocity','dev.human_direction')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    recording={'channels':[{'name':name,'unit':'source_bound_structured',
        'sampling_rate_hz':20,'method':'original Native pose, context and four-camera frame join',
        'time_window':'all 600 frames','reference_frame':'original Native frame',
        'uncertainty':'50 ms frame bracket; visible driver hand signal and lamp pixels need independent review'}
        for name in CHANNELS],
        'context_inputs':[{'name':'emergency_context','unit':'structured',
                           'method':'independent emergency authorization and flashing-light review'},
                          {'name':'preparing_to_move_context','unit':'structured',
                           'method':'independent source-driver hand pixels, actor identity and window geometry review'},
                          {'name':'officer_direction_context','unit':'structured',
                           'method':'original officer identity, instruction, recipient and timing review'}],
        'limitations':['Requested motion and synthetic fixtures cannot establish visible original pixels or legal outcome']}
    candidates=[]
    for candidate_id,gap,height,fov in (('primary',-20,0,90),('fallback1',-25,0,90),
                                        ('fallback2',-20,1.0,105)):
        cfg={'assignment_id':AID,'case_id':CASE,'selected_case_id':CASE,
            'case_suffix':'preparing_hand_signal','candidate_id':candidate_id,
            'law_id':'NRS-484B-267-2d','cell_id':'C404492','actor':'motor_vehicle_driver',
            'frames':600,'rate_hz':20,'duration_s':30,
            'engineering_initial_ego_gap_m':gap,'camera_height_offset_m':height,
            'camera_fov_deg':fov,
            'cameras':[{'name':name,'width':1920 if name=='overview' else 1280,
                        'height':1080 if name=='overview' else 720,
                        'pose_strategy':'surveyed_world_transform','fov_deg':90} for name in CAMERAS],
            'physical_acceptance_claimed':False,'required_atoms':[],
            'reference_vehicle_kind':'authorized_emergency_vehicle',
            'reference_motion_request':{'stopped_frames':[0,79],
                                        'visible_preparation_frames':[80,119],
                                        'subsequent_moving_frames':[120,599]},
            'recording_description':recording}
        files=[{'path':'runner.py','content':(HERE/'native/hand_signal_runner.py').read_text()},
               {'path':'tests/test_native.py','content':(HERE/'native/tests/test_native.py').read_text()},
               {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
               {'path':'measure_emergency.py','content':(HERE/'measure_emergency.py').read_text()},
               {'path':'finalize.py','content':(HERE/'native/hand_signal_finalize.py').read_text()}]
        construction={'format':'worker-construction','assignment_id':AID,'case_id':CASE,
            'law_id':'NRS-484B-267-2d','cell_id':'C404492','actor':'motor_vehicle_driver',
            'entrypoint':'runner.py','recording_description':recording,
            'measurement_plan':{'entrypoint':'measure_emergency.py',
                'statutory_branch':'emergency_preparing_hand_signal',
                'sources':['video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl',
                           'emergency_context.json'],
                'same_direction_cutoff':None,'abreast_cutoff':None,'legal_result':None},
            'static_checks':['exact emergency and visible-preparation survey, map and adjacent-lane review'],
            'termination_rules':['retain exactly 600 synchronized 20-Hz original frames'],
            'mechanisms':['survey-gated adjacent-lane emergency vehicle and authored driver-arm mesh capture',
                          'requested 120-frame stop including 40-frame visible driver hand signal and subsequent travel',
                          'source-joined original body geometry, signal actor identity and independent hand-pixel review'],
            'files':files}
        path=HERE/'draft-preparing-hand-signal'/candidate_id/'construction.json'
        write(path,construction)
        if candidate_id!='primary':
            trigger=({'source':'original Native pose and lane survey',
                      'metric':'measured following gap during source preparation',
                      'failure_condition':'subject does not remain behind the source vehicle'}
                     if candidate_id=='fallback1' else
                     {'source':'original four-camera frame map and pixels',
                      'metric':'visible driver hand signal and flashing-light pixels',
                      'failure_condition':'review cannot distinguish the source driver hand signal or lamps'})
            candidates.append({'id':candidate_id,'construction':str(path.relative_to(HERE)),
                'construction_sha256':sha(path),'trigger':trigger,
                'changed_knobs':(['initial ego gap -20 m to -25 m'] if candidate_id=='fallback1'
                                 else ['camera height +1 m','camera FOV 90 to 105 degrees'])})
    primary=HERE/'draft-preparing-hand-signal/primary/construction.json'
    manifest={'format':'worker-statutory-alternative-draft-v1','assignment_id':AID,
        'status':'partial','cases':[{'case_id':CASE,'kind':'unselected_cpu_draft_not_delivery_ready',
            'source_branch':'same-direction visibly preparing emergency vehicle driver hand signal',
            'construction':str(primary.relative_to(HERE)),
            'construction_sha256':sha(primary),'candidates':candidates,
            'delivery_readiness':'incomplete'}]}
    write(HERE/'draft-preparing-hand-signal-manifest.json',manifest)
    print(json.dumps({'cases':1,'candidate_constructions':3,
                      'manifest_sha256':sha(HERE/'draft-preparing-hand-signal-manifest.json')},sort_keys=True))


if __name__=='__main__':main()
