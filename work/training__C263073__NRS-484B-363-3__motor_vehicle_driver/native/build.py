"""Package exact C263073 sources and original Native CPU drafts."""
import hashlib
import json
import copy
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ASSIGNMENT=ROOT.name
CAMERAS=['overview','approach','reference_corner','driver_reference']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=ASSIGNMENT+'__'+suffix
        description={'rate_hz':20,'duration_s':30,'cameras_required':CAMERAS,
            'channels':[{'name':name,'unit':'structured' if name not in ('kin.heading','drv.within_signed_zone') else
                         ('deg' if name=='kin.heading' else 'boolean'),
                         'sampling_rate_hz':20,'method':'original Native motion plus independent source review',
                         'time_window':'full 30-second attempt','reference_frame':'Native frame',
                         'uncertainty':'physical and legal interpretation pending'}
                        for name in ('dev.zone_sign','drv.within_signed_zone','drv.u_turn','kin.heading',
                                     'ru.child','dev.speed_limit_beacon','drv.condition_in_effect','env.civil_time')],
            'context_inputs':[],
            'required_original_sources':['Native vehicle trajectory and heading','school-zone designation and boundary',
                'child identities and locations','session, operation, class-hour and civil-time records',
                'beacon and sign-state record','all five exception dispositions','four synchronized original cameras'],
            'limitations':['Driven path remains physically unconfirmed until CARLA and original pixel review',
                'Generic walker blueprint does not establish child identity or legal presence',
                'Diagnostic zone outline is not official designation',
                'No legal heading threshold or presence radius is adopted']}
        camera_specs=[{'name':name,'width':1920 if name=='overview' else 1280,
            'height':1080 if name=='overview' else 720,'fov_deg':85,
            'pose_strategy':'ego-relative driver view' if name=='driver_reference' else
                'fixed world view of original school-zone road and participants'} for name in CAMERAS]
        config={'case_id':case_id,'selected_case_id':case_id,
            'supported_case_ids':[ASSIGNMENT+'__controlled_1',ASSIGNMENT+'__controlled_2'],
            'case_suffix':suffix,'cell_id':'C263073','law_id':'NRS-484B-363-3',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'cameras':camera_specs,
            'required_atoms':[],'source_packets':[],
            'vehicle_blueprint':'vehicle.tesla.model3',
            'target':'defer U-turn and continue' if suffix=='controlled_1' else 'physically driven U-turn target within authored zone'}
        config['case']={'case_id':case_id,'recording_description':description}
        config['physical_completion']=(
            {'criterion':'turn','motion_source':'native-motion.jsonl',
             'body_key':'ego.body_xy_m','heading_key':'ego.heading_deg',
             'turn_degrees':180,'turn_tolerance_deg':30,
             'minimum_progress_m':5,'minimum_samples':20,
             'engineering_tolerances_not_legal':True,'context_sources':['school-context.json']}
            if suffix=='controlled_2' else
            {'criterion':'travel_progress','motion_source':'native-motion.jsonl',
             'body_key':'ego.body_xy_m','minimum_progress_m':5,'minimum_samples':20,
             'engineering_tolerances_not_legal':True,'context_sources':['school-context.json']})
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','drive.py','runner.py','measure_turn.py','review_context.py','finalize.py',
                     'tests/test_native.py','tests/test_drive.py','tests/test_review_context.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name;files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C263073','law_id':'NRS-484B-363-3',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':description,
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored two-way OpenDRIVE road','600-frame physically simulated path target',
                'one separate person position','four synchronized FFV1 cameras',
                'source-bound raw trajectory measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        fallback=copy.deepcopy(proposal)
        fallback['files'][0]['content']=json.dumps({**config,'vehicle_blueprint':'vehicle.mini.cooper_s'},indent=2)+'\n'
        fallback['candidate_id']='fallback1'
        fallback_target=HERE/'bundles'/suffix/'fallback1-construction.json'
        fallback_target.write_text(json.dumps(fallback,indent=2)+'\n')
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'physical','reason':'Original driven turn may fail to track the narrow two-way road envelope'},
            'candidates':[{'id':'fallback1','construction':str(fallback_target.relative_to(ROOT)),
                'construction_sha256':sha(fallback_target),
                'trigger':{'source':'original Native ego body and heading readback',
                    'metric':'U-turn tracking and roadway containment after complete source review',
                    'failure_condition':'primary fails to complete the requested path within the authored envelope'},
                'changed_knobs':['vehicle blueprint Tesla Model 3 to Mini Cooper S for turn-radius tracking']}],
            'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
