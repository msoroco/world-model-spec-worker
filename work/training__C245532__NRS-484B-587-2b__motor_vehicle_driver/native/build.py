"""Package exact C245532 sources and original Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ASSIGNMENT=ROOT.name
CAMERAS=[{'name':'overview','width':1920,'height':1080,'pose_strategy':'entire two-lane route','fov_deg':85},
    {'name':'approach','width':1280,'height':720,'pose_strategy':'entrance-lane approach','fov_deg':85},
    {'name':'reference_corner','width':1280,'height':720,'pose_strategy':'solid-white separator','fov_deg':85},
    {'name':'driver_reference','width':1280,'height':720,'pose_strategy':'driver and departure lane','fov_deg':85}]
TERMS=('st.lane_marking','st.controlled_access','drv.straddles_marking','drv.lane_change',
    'rel.occupies','st.shoulder','ru.emergency_vehicle','ru.transit_bus')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    suffixes=('controlled_1','controlled_2','emergency_1','emergency_2')
    for suffix in suffixes:
        case_id=ASSIGNMENT+'__'+suffix
        description={'channels':[{'name':term,'unit':'structured','sampling_rate_hz':20,
            'method':'same-tick original Native geometry or retained source-context review',
            'time_window':'600 frames','reference_frame':'Native world XY and reviewed authority context',
            'uncertainty':'Physical and legal status require independent review'} for term in TERMS],
            'context_inputs':[{'name':'separator_context','unit':'structured',
            'method':'original source and public-authority review'}],
            'limitations':['Original Native physics and camera visibility remain unverified',
                'Authored motorway metadata does not prove legal controlled-access status']}
        config={'case_id':case_id,'selected_case_id':case_id,'case':{'case_id':case_id},
            'case_suffix':suffix,'cell_id':'C245532','law_id':'NRS-484B-587-2b',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'frames':600,
            'cameras':CAMERAS,'required_atoms':[],'source_packets':[],
            'supported_case_ids':[ASSIGNMENT+'__'+item for item in suffixes],
            'recording_description':description,
            'target':'remain on entrance-lane side' if suffix=='controlled_1' else 'move across separator into traffic lane',
            'emergency_obstacle_requested':suffix=='emergency_2'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_separator.py','finalize_separator.py','tests/test_native.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name;files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C245532','law_id':'NRS-484B-587-2b',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':description,
            'measurement_plan':{'method':'600-frame original body and lane readback with separately reviewed highway and separator context',
                'output':'four source-hashed saved measurement objects','legal_cutoff_defined':False},
            'termination_rules':['600 source frames and four synchronized camera streams',
                'close encoders and restore world before sealed capture'],
            'mechanisms':['authored two same-direction lanes with solid-white separator',
                'target velocity changes lateral motion for crossing cases',
                'emergency_2 alone requests a stopped obstruction ahead in the entrance lane; emergency_1 retains the same crossing without it',
                'PipelineCapture and original Native frame map',
                'recorded-only finalizer with four distinct source-bound methods'],
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored same-direction two-lane OpenDRIVE','solid white separator',
                '600 original Native frames','four synchronized FFV1 cameras',
                'source-bound raw body and lane-transition measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'none','reason':'No measured original Native motion or camera failure trigger exists yet; public authority and official lane function are evidence reviews, not fallback construction knobs'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
