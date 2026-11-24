"""Build separate source-reviewed regulatory vehicle moving alternatives."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
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
        'uncertainty':'50 ms frame bracket; regulatory status and lamp qualification require independent review'}
        for name in CHANNELS],
        'context_inputs':[{'name':'regulatory_vehicle_context','unit':'structured',
                           'method':'independent regulatory agency vehicle and qualifying flashing-light review'},
                          {'name':'officer_direction_context','unit':'structured',
                           'method':'original officer identity, instruction, recipient and timing review'}],
        'limitations':['Synthetic fixture cannot establish regulatory status, physical realization or legal outcome']}
    entries=[]
    for suffix in ('official_1','official_2'):
        case=AID+'__'+suffix
        candidates=[]
        for candidate_id,gap,height,fov in (('primary',-20,0,90),('fallback1',-25,0,90),
                                            ('fallback2',-20,1.0,105)):
            cfg={'assignment_id':AID,'case_id':case,'selected_case_id':case,
                'case_suffix':suffix,'candidate_id':candidate_id,'law_id':'NRS-484B-267-2d',
                'cell_id':'C404492','actor':'motor_vehicle_driver','frames':600,
                'rate_hz':20,'duration_s':30,'engineering_initial_ego_gap_m':gap,
                'camera_height_offset_m':height,'camera_fov_deg':fov,
                'cameras':[{'name':n,'width':1920 if n=='overview' else 1280,
                            'height':1080 if n=='overview' else 720,
                            'pose_strategy':'surveyed_world_transform','fov_deg':90} for n in CAMERAS],
                'physical_acceptance_claimed':False,'required_atoms':[],
                'reference_vehicle_kind':'official_regulatory_vehicle',
                'recording_description':recording}
            files=[{'path':'runner.py','content':(HERE/'native/runner.py').read_text()},
                   {'path':'tests/test_native.py','content':(HERE/'native/tests/test_native.py').read_text()},
                   {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
                   {'path':'measure_emergency.py','content':(HERE/'measure_emergency.py').read_text()},
                   {'path':'finalize.py','content':(HERE/'finalize.py').read_text()}]
            construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
                'law_id':'NRS-484B-267-2d','cell_id':'C404492','actor':'motor_vehicle_driver',
                'entrypoint':'runner.py','recording_description':recording,
                'measurement_plan':{'entrypoint':'measure_emergency.py',
                    'statutory_branch':'regulatory_moving',
                    'sources':['video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl',
                               'emergency_context.json'],
                    'same_direction_cutoff':None,'abreast_cutoff':None,'legal_result':None},
                'static_checks':['exact regulatory vehicle survey, map and adjacent-lane review'],
                'termination_rules':['retain exactly 600 synchronized 20-Hz original frames'],
                'mechanisms':['survey-gated adjacent-lane regulatory vehicle capture',
                              'independently reviewed regulatory authority and flashing equipment',
                              'source-joined original body geometry'],
                'files':files}
            path=HERE/'draft-official'/suffix/candidate_id/'construction.json'
            write(path,construction)
            if candidate_id!='primary':
                trigger=({'source':'original Native pose and lane survey',
                          'metric':'measured following trajectory and body gap',
                          'failure_condition':'subject does not remain behind during the approach'}
                         if candidate_id=='fallback1' else
                         {'source':'original four-camera frame map and pixels',
                          'metric':'visible regulatory body and lamp pixels',
                          'failure_condition':'review cannot identify regulatory vehicle or flashing equipment'})
                candidates.append({'id':candidate_id,'construction':str(path.relative_to(HERE)),
                    'construction_sha256':sha(path),'trigger':trigger,
                    'changed_knobs':(['initial ego gap -20 m to -25 m'] if candidate_id=='fallback1'
                                     else ['camera height +1 m','camera FOV 90 to 105 degrees'])})
        primary=HERE/'draft-official'/suffix/'primary'/'construction.json'
        entries.append({'case_id':case,'kind':'unselected_cpu_draft_not_delivery_ready',
            'source_branch':'same-direction moving official vehicle of a regulatory agency',
            'construction':str(primary.relative_to(HERE)),
            'construction_sha256':sha(primary),'candidates':candidates,
            'delivery_readiness':'incomplete'})
    manifest={'format':'worker-statutory-alternative-draft-v1','assignment_id':AID,
              'status':'partial','cases':entries}
    write(HERE/'draft-official-manifest.json',manifest)
    print(json.dumps({'cases':len(entries),'candidate_constructions':6,
                      'manifest_sha256':sha(HERE/'draft-official-manifest.json')},sort_keys=True))


if __name__=='__main__':main()
