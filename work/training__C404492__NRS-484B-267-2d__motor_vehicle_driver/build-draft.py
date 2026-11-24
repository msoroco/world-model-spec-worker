"""Build two source-preserving Native controlled primaries for emergency travel."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('drv.responding_emergency','rel.same_direction','rel.longitudinal_overlap',
          'drv.overtaking','rel.ahead_behind_in_lane','kin.velocity','dev.human_direction')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    recording={'channels':[{'name':name,'unit':'source_bound_structured',
        'sampling_rate_hz':20,'method':'original Native pose, context and four-camera frame join',
        'time_window':'all 600 frames','reference_frame':'original Native frame',
        'uncertainty':'50 ms frame bracket; statutory qualification requires independent review'}
        for name in CHANNELS],
        'context_inputs':['independent emergency authorization and qualifying flashing-light review',
                          'original officer direction review'],
        'limitations':['Synthetic fixture cannot establish physical realization or legal outcome']}
    entries=[]
    for suffix,gap in (('controlled_1',-20),('controlled_2',-20)):
        case=AID+'__'+suffix
        contract={'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-267-2d',
                'source':'NRS 484B.267(2)(d); with 484B.267(4)',
                'output_key':'per_frame_geometry','method':'source_joined_same_direction_abreast_and_order',
                'value_type':'array','kind':'measured',
                'inputs':['video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl','emergency_context.json',
                          'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv']}],
            'negative':{'remove':['vehicle_poses.jsonl'],
                        'error_contains':'Missing required source: vehicle_poses.jsonl'},
            'legal_result':None,'original_source_review_required':True}
        contract_path=HERE/'measurement-contracts'/(suffix+'.json')
        write(contract_path,contract)
        candidates=[]
        for candidate_id,candidate_gap,height,fov in (('primary',gap,0,90),('fallback1',-25,0,90),('fallback2',gap,1.0,105)):
            cfg={'assignment_id':AID,'case_id':case,'selected_case_id':case,
            'case_suffix':suffix,'candidate_id':candidate_id,'law_id':'NRS-484B-267-2d',
            'cell_id':'C404492','actor':'motor_vehicle_driver','frames':600,
            'rate_hz':20,'duration_s':30,'engineering_initial_ego_gap_m':candidate_gap,
            'camera_height_offset_m':height,'camera_fov_deg':fov,
            'cameras':[{'name':n,'width':1920 if n=='overview' else 1280,
                        'height':1080 if n=='overview' else 720,
                        'pose_strategy':'surveyed_world_transform','fov_deg':90} for n in CAMERAS],
            'physical_acceptance_claimed':False,'required_atoms':[],'source_packets':[],
            'recording_description':recording}
            files=[{'path':name,'content':(HERE/'native'/name).read_text()} for name in ('runner.py','tests/test_native.py')]
            files.append({'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'})
            files.append({'path':'measure_emergency.py','content':(HERE/'measure_emergency.py').read_text()})
            files.append({'path':'finalize.py','content':(HERE/'finalize.py').read_text()})
            files.append({'path':'measurement-contract.json','content':contract_path.read_text()})
            construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
            'law_id':'NRS-484B-267-2d','cell_id':'C404492','actor':'motor_vehicle_driver',
            'entrypoint':'runner.py','recording_description':recording,
            'measurement_plan':{'entrypoint':'measure_emergency.py','sources':[
                'video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl','emergency_context.json'],
                'same_direction_cutoff':None,'abreast_cutoff':None,'legal_result':None},
            'static_checks':['case, candidate, camera profile and Native lane survey'],
            'termination_rules':['retain exactly 600 synchronized 20-Hz original frames'],
            'mechanisms':['survey-gated adjacent-lane two-vehicle capture',
                          'source-joined saved geometry and independent qualification review'],
            'files':files}
            path=HERE/'draft-emergency'/suffix/candidate_id/'construction.json';write(path,construction)
            if candidate_id!='primary':
                trigger=({'source':'original Native pose and lane survey','metric':'measured following trajectory and body gap','failure_condition':'subject cannot remain behind the emergency body during the approach frames'} if candidate_id=='fallback1' else {'source':'original four-camera pixels and frame map','metric':'independent subject/emergency body and lamp visibility','failure_condition':'review cannot see both bodies and flashing lamp pixels across the controlled episode'})
                candidates.append({'id':candidate_id,'construction':str(path.relative_to(HERE)),'construction_sha256':sha(path),'trigger':trigger,'changed_knobs':(['initial ego gap -20 m to -25 m'] if candidate_id=='fallback1' else ['camera height +1 m','camera FOV 90 to 105 degrees'])})
        entries.append({'case_id':case,'kind':'selected_cpu_draft_not_delivery_ready',
            'measurement_contract':str(contract_path.relative_to(HERE)),
            'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'source-bound-emergency-abreast-v1'},
            'construction':str((HERE/'draft-emergency'/suffix/'primary'/'construction.json').relative_to(HERE)),
            'construction_sha256':sha(HERE/'draft-emergency'/suffix/'primary'/'construction.json'),
            'candidate_risk':{'status':'physical','reason':'Authorization, qualifying lamp equipment, actual flash pixels and original same-direction Native travel require review'},
            'candidates':candidates,'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':AID,
        'status':'partial','cases':entries}
    write(HERE/'draft-emergency-manifest.json',manifest)
    print(json.dumps({'case_hashes':{e['case_id']:e['construction_sha256'] for e in entries},
                      'manifest_sha256':sha(HERE/'draft-emergency-manifest.json')},sort_keys=True))


if __name__=='__main__':main()
