"""Build paired one-lane-each-direction slow-traffic Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
CASES=(('controlled_1',True),('controlled_2',False))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    entries=[]
    for suffix,right in CASES:
        case=ASSIGNMENT+'__'+suffix
        config={'case_id':case,'selected_case_id':case,'supported_case_ids':[case],
                'candidate_id':'primary','law_id':'NRS-484B-627-1a','cell_id':'C230259',
                'actor':'motor_vehicle_driver','extreme_right_requested':right,
                'rate_hz':20,'duration_s':30,'required_atoms':[],'source_packets':[],
                'case':{'case_id':case},
                'cameras':[{'name':name,'width':1280,'height':720} for name in
                    ('overview','approach','reference_corner','driver_reference')],
                'recording_description':{'channels':[
                    {'name':'participant_footprints','unit':'structured','sampling_rate_hz':20,
                     'method':'original Native actor bounding boxes and transforms',
                     'time_window':'600 frames','reference_frame':'two-way paved highway draft',
                     'uncertainty':'50 ms frame interval'},
                    {'name':'participant_velocity_and_intent','unit':'m/s','sampling_rate_hz':20,
                     'method':'original Native actor velocity and controller command readback',
                     'time_window':'600 frames','reference_frame':'same highway segment',
                     'uncertainty':'controller intent is not proof of actual impediment'}],
                     'limitations':['Slow/impede and extreme right are legal findings, not numeric thresholds',
                                    'Public highway status, sufficient paved width and NRS 484B.630 applicability need independent sources',
                                    'Physical follower reaction and camera pixels remain unverified']},
                'status':'partial_cpu_draft'}
        files=[{'path':name,'content':(HERE/'native'/name).read_text()}
               for name in ('runner.py','geometry.py','tests/test_native.py')]
        files.append({'path':'slow_traffic_saved_measure.py',
                      'content':(HERE/'slow_traffic_saved_measure.py').read_text()})
        files.append({'path':'finalize.py',
                      'content':(HERE/'finalize.py').read_text()})
        files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
        construction={'case_id':case,'law_id':config['law_id'],'cell_id':config['cell_id'],
            'actor':config['actor'],'entrypoint':'runner.py','files':files,
            'recording_description':config['recording_description'],
            'measurement_plan':{'entrypoint':'finalize.py',
                'required_sources':['slow-traffic-trace.jsonl','slow-traffic-context.json',
                                    'road.xodr','video_frames.jsonl'],
                'source_review_required':True},
            'static_checks':['160m one-lane-each-way road with 3m paved right margin',
                             'subject and immediate follower','four cameras and 600 original frames'],
            'termination_rules':['600 original frames','restore world and destroy owned actors'],
            'mechanisms':['same subject longitudinal speed and follower policy in both cases',
                          'subject lateral movement '+('toward right paved edge' if right else 'absent'),
                          'no legal impediment, extreme-right or NRS 484B.630 conclusion'],
            'status':'partial_native_execution_cpu_checked_physical_unverified'}
        path=HERE/'draft-slow-traffic'/suffix/'primary'/'construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(construction,indent=2)+'\n')
        contract={'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-627-1a',
                'source':'NRS 484B.627(1)(a)','output_key':'slow_traffic_observation',
                'method':'slow_traffic_observation','value_type':'object','kind':'measured',
                'inputs':['slow-traffic-trace.jsonl','video_frames.jsonl',
                          'slow-traffic-context.json','road.xodr']}],
            'negative':{'remove':['slow-traffic-context.json'],
                'error_contains':'Missing required source: slow-traffic-context.json'}}
        contract_path=HERE/('measurement-'+suffix+'.json')
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        entries.append({'case_id':case,'kind':'delivery',
            'construction':str(path.relative_to(HERE)),
            'construction_sha256':sha(path),
            'measurement_contract':contract_path.name,
            'measurement_procedure':{'entrypoint':'finalize.py',
                                     'output_schema':'c230259-source-analysis-v1'},
            'candidate_risk':{'status':'physical',
                'reason':'Paved edge, actual following impediment and rightward trajectory need Native review'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1',
              'assignment_id':ASSIGNMENT,
              'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
              'status':'partial','cases':entries}
    (HERE/'draft-slow-traffic-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':[{'case_id':e['case_id'],'construction_sha256':e['construction_sha256']}
                                for e in entries],
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))


if __name__=='__main__':
    main()
