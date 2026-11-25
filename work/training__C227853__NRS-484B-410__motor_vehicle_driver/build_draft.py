"""Build clear/conflict primary Native drafts with the same ego departure policy."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
CASES=(('controlled_1',False),('controlled_2',True))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    entries=[]
    for suffix,conflict in CASES:
        case=ASSIGNMENT+'__'+suffix
        config={'case_id':case,'selected_case_id':case,'supported_case_ids':[case],
                'candidate_id':'primary','law_id':'NRS-484B-410','cell_id':'C227853',
                'actor':'motor_vehicle_driver','approaching_conflict_requested':conflict,
                'rate_hz':20,'duration_s':30,'required_atoms':[],'source_packets':[],
                'case':{'case_id':case},
                'cameras':[{'name':name,'width':1920 if name=='overview' else 1280,
                            'height':1080 if name=='overview' else 720} for name in
                    ('overview','approach','reference_corner','driver_reference')],
                'recording_description':{'channels':[
                    {'name':'participant_footprints','unit':'structured','sampling_rate_hz':20,
                     'method':'original Native actor bounding boxes and transforms',
                     'time_window':'600 frames','reference_frame':'curbside highway',
                     'uncertainty':'50 ms frame interval'},
                    {'name':'participant_velocity','unit':'m/s','sampling_rate_hz':20,
                     'method':'original Native actor velocity readback',
                     'time_window':'600 frames','reference_frame':'curbside highway',
                     'uncertainty':'physics and identity require physical review'}],
                     'context_inputs':[],
                     'limitations':['Safety is a legal judgment, never a numeric gap cutoff',
                                    'Highway dedication, parking permission and purpose require sources',
                                    'Physical curb and camera pixels remain unverified']},
                'status':'partial_cpu_draft'}
        files=[{'path':name,'content':(HERE/'native'/name).read_text()}
               for name in ('runner.py','geometry.py','source_context.py','tests/test_native.py')]
        files.append({'path':'departure_saved_measure.py',
                      'content':(HERE/'departure_saved_measure.py').read_text()})
        files.append({'path':'finalize.py',
                      'content':(HERE/'finalize.py').read_text()})
        files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
        construction={'case_id':case,'law_id':config['law_id'],'cell_id':config['cell_id'],
            'actor':config['actor'],'entrypoint':'runner.py','files':files,
            'recording_description':config['recording_description'],
            'measurement_plan':{'entrypoint':'finalize.py',
                'required_sources':['departure-trace.jsonl','departure-context.json',
                                    'road.xodr','video_frames.jsonl'],
                'source_review_required':True},
            'static_checks':['160m curbside departure road','two vehicle trajectories',
                             'four cameras and 600 original frames'],
            'termination_rules':['600 original frames','restore world and destroy owned actors'],
            'mechanisms':['same ego departure policy; other traffic initial gap '+
                          ('near' if conflict else 'far'),
                          'no safety verdict or physical completion claim'],
            'status':'partial_native_execution_cpu_checked_physical_unverified'}
        path=HERE/'draft-departure'/suffix/'primary'/'construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(construction,indent=2)+'\n')
        entries.append({'case_id':case,'kind':'delivery',
            'construction':str(path.relative_to(HERE)),
            'construction_sha256':sha(path),
            'candidate_risk':{'status':'physical',
                'reason':'Curb contact, merge trajectory and traffic clearance need Native review'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1',
              'assignment_id':ASSIGNMENT,
              'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
              'status':'partial','cases':entries}
    (HERE/'draft-departure-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':[{'case_id':e['case_id'],'construction_sha256':e['construction_sha256']}
                                for e in entries],
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))


if __name__=='__main__':
    main()
