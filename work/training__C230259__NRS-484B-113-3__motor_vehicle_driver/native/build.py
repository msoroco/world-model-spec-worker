"""Package exact C230259 sources and original Native CPU drafts."""
import hashlib
import json
import copy
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ASSIGNMENT=ROOT.name
CAMERAS=[{'name':'overview','width':1920,'height':1080,'pose_strategy':'fixed elevated road corridor','fov_deg':85},
    {'name':'approach','width':1280,'height':720,'pose_strategy':'fixed ego backing approach','fov_deg':85},
    {'name':'reference_corner','width':1280,'height':720,'pose_strategy':'fixed moving road user corridor','fov_deg':85},
    {'name':'driver_reference','width':1280,'height':720,'pose_strategy':'fixed side conflict view','fov_deg':85}]
CHANNELS=['drv.backing','drv.yields_to','ru.pedestrian','kin.velocity','drv.arrival_order',
    'drv.time_to_conflict','drv.hard_deceleration','backing_onset_s',
    'native_body_pose_control','camera_frame_join']


def recording_description():
    return {'channels':[{'name':name,'unit':'s' if name=='backing_onset_s' else 'structured','sampling_rate_hz':20,
        'method':'retained original Native actor and frame-map sample',
        'time_window':'30 s / 600 joined frames','reference_frame':'Native map and original frame',
        'uncertainty':'50 ms sample; actual pixels and legal precedence unverified'} for name in CHANNELS],
        'context_inputs':[{'name':'road_and_actor_context','unit':'structured',
            'method':'authored highway lane readback and original actor identity'}],
        'limitations':['Synthetic diagnostics do not establish CARLA motion, physical visibility or a legal verdict']}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2','pedestrian_1','pedestrian_2'):
        case_id=ASSIGNMENT+'__'+suffix
        pedestrian=suffix.startswith('pedestrian_')
        config={'case_id':case_id,'selected_case_id':case_id,
            'supported_case_ids':[ASSIGNMENT+'__'+s for s in ('controlled_1','controlled_2','pedestrian_1','pedestrian_2')],
            'case':{'case_id':case_id},'case_suffix':suffix,'candidate_id':'primary',
            'cell_id':'C230259','law_id':'NRS-484B-113-3',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,
            'required_atoms':['kin.velocity'],'source_packets':[],'mandatory_channels':CHANNELS,
            'physical_completion':{'criterion':'travel_progress','motion_source':'native-motion.jsonl',
                'position_key':'ego.center_xy_m','minimum_progress_m':1.0,'minimum_samples':2,
                'context_sources':['traffic-context.json'],
                'completion_goal_method':'Measured original backing path exceeds 1 m; engineering completion only.'},
            'recording_description':recording_description(),'cameras':CAMERAS,
            'target':('wait before backing while pedestrian passes' if suffix=='pedestrian_1' else
                'back while pedestrian approaches' if suffix=='pedestrian_2' else
                'wait before backing while moving vehicle passes' if suffix=='controlled_1' else
                'back while moving vehicle approaches')}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_motion.py','measure_pedestrian.py','finalize.py','audit.py','tests/test_native.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name;files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C230259','law_id':'NRS-484B-113-3',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':recording_description(),
            'measurement_plan':{'source':'native-motion.jsonl','finalizer':'measure_pedestrian.py' if pedestrian else 'measure_motion.py'},
            'termination_rules':['600 joined original frames, 30 s at 20 Hz'],
            'mechanisms':['script-controlled ego backing onset','separate moving vehicle','pedestrian walker on pedestrian cases'],
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored OpenDRIVE highway','ego backing phase',
                'separate moving-vehicle phase','600 original Native frames',
                'four synchronized FFV1 cameras','source-bound raw timing measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        alternatives=[]
        for candidate_id,knob,value,trigger in (
            ('fallback1','other_start_x_m',-45,'Other vehicle reaches conflict region before usable backing observation'),
            ('fallback2','ego_start_x_m',27,'Ego backing trajectory fails to enter authored conflict region')):
            alternate=copy.deepcopy(proposal)
            alternative_config={**config,knob:value,'candidate_id':candidate_id}
            alternate['files'][0]['content']=json.dumps(alternative_config,indent=2)+'\n'
            alternate['engineering_variant']={'id':candidate_id,'knob':knob,'value':value}
            destination=HERE/'bundles'/suffix/candidate_id/'construction.json'
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(alternate,indent=2)+'\n')
            alternatives.append({'id':candidate_id,'construction':str(destination.relative_to(ROOT)),
                'construction_sha256':sha(destination),'changed_knobs':[knob],
                'trigger':{'source':'original Native motion and frame-map audit',
                    'metric':'first conflict-region frame and active backing frame count',
                    'failure_condition':trigger},'offline_pending':True,'compatibility_pending':True})
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'physical',
                'reason':'Backing path and pedestrian encounter unverified' if pedestrian else 'Backing path and moving traffic response unverified'},
            'candidates':alternatives,'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
