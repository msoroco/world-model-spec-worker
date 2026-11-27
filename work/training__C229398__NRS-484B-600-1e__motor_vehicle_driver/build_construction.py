"""Materialize three exact approach-to-curb speed constructions."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
FILES=('runner.py','road_geometry.py','source_review.py','saved_measure.py',
       'finalize.py','tests/test_current_runner.py','tests/test_saved_measure.py')
CHANNELS=('kin.speed','kin.velocity','ru.subject')
SPEEDS=(75.0,79.5,85.0)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    recording={'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':'Original Native actor, velocity and lane frames joined with hashed route, phase, subject and four-view visibility sources',
        'time_window':'600 frames; statute measured only in reviewed driving approach frames',
        'reference_frame':'authored C229398 road with Native readback',
        'uncertainty':'Requested speed does not establish achieved velocity; original same-cell phase and curb completion require independent review'} for name in CHANNELS],
        'context_inputs':[],
        'limitations':['Parked frames are excluded from the speed-limit measurement',
            'Synthetic diagnostic sources do not establish physical or legal acceptance']}
    cameras=[{'name':name,'width':width,'height':height,'fps':20,'fov_deg':fov,
        'location_xyz_m':xyz,'rotation_pyr_deg':rotation,
        'pose_strategy':'vehicle_attached_continuous_approach_and_curb'}
        for name,width,height,fov,xyz,rotation in (
            ('overview',1920,1080,95,[-7,0,5],[-20,0,0]),
            ('approach',1280,720,85,[2,0,2],[-3,0,0]),
            ('reference_corner',1280,720,95,[-3,3,2],[-8,-45,0]),
            ('driver_reference',1280,720,95,[-3,0,2],[0,180,0]))]
    for i,speed in enumerate(SPEEDS,1):
        suffix=f'probe_0{i}'
        case=AID+'__'+suffix
        directory=HERE/'cases'/suffix
        config={'case_id':case,'law_id':'NRS-484B-600-1e','cell_id':'C229398',
                'actor':'motor_vehicle_driver','frozen_cell':{'layout':'road',
                'maneuver':'park','control':'curb'},
                'status':'cpu_prepared_original_capture_pending',
                'requested_approach_speed_mph':speed,
                'rate_hz':20,'duration_s':30,'frames':600,
                'required_atoms':['kin.position','kin.speed'],
                'source_packets':[],
                'physical_acceptance_claimed':False,'legal_verdict':None,
                'cameras':cameras,'assignment_id':AID,'selected_case_id':case,
                'supported_case_ids':[AID+f'__probe_0{n}' for n in range(1,4)],
                'ego_blueprint':'vehicle.tesla.model3',
                'recording_description':recording,
                'case':{'case_id':case,'recording_description':recording}}
        write(directory/'config.json',config)
        files=[{'path':name,'content':(HERE/name).read_text()} for name in FILES]
        files.append({'path':'config.json','content':(directory/'config.json').read_text()})
        construction={'format':'worker-inline-construction','case_id':case,
            'law_id':'NRS-484B-600-1e','cell_id':'C229398',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py',
            'files':files,'recording_description':recording,
            'measurement_plan':{'entrypoint':'finalize.py','source_review_required':True,
                'required_sources':['approach-review.json','visibility-review.json',
                    'native-speed.jsonl','video_frames.jsonl','trace.jsonl','road.xodr',
                    'source_context/road_curb_route.txt','source_context/approach_scope.txt',
                    'source_context/vehicle_identity.txt','source_context/camera_visibility.txt']},
            'static_checks':['One 1.8-km road has a driving lane and curb parking lane',
                'One continuous 600-frame recording has approach, curb-parking and parked phases',
                'Four synchronized 20-Hz source cameras'],
            'mechanisms':['Native velocity and road/lane readback after each tick',
                'Hashed original road/curb, temporal phase, actor and camera source review',
                'Driving approach measured separately from requested speed and parked phase'],
            'termination_rules':['600 Native frames','Destroy owned actors and restore world'],
            'status':'cpu_construction_physical_unverified'}
        write(directory/'construction.json',construction)
        if i==1:
            write(HERE/'config.json',config)
            write(HERE/'construction.json',construction)
    print(json.dumps({'selected_case_ids':[AID+f'__probe_0{i}' for i in range(1,4)]}))


if __name__=='__main__':
    main()
