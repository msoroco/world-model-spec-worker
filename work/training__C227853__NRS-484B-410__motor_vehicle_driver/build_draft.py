"""Build clear/conflict primary Native drafts with the same ego departure policy."""
import hashlib
import json
import copy
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
CASES=(('controlled_1',False,'parked_no_loading',True),
       ('controlled_2',True,'parked_no_loading',True),
       ('controlled_3',False,'stopped_temporary',True),
       ('controlled_4',True,'stopped_temporary',True),
       ('controlled_5',False,'standing_passenger_exchange',True),
       ('controlled_6',True,'standing_passenger_exchange',True),
       ('controlled_7',False,'parked_no_loading',False),
       ('controlled_8',True,'parked_no_loading',False),
       ('controlled_9',False,'stopped_temporary',False),
       ('controlled_10',True,'stopped_temporary',False),
       ('controlled_11',False,'standing_passenger_exchange',False),
       ('controlled_12',True,'standing_passenger_exchange',False))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    entries=[]
    for suffix,conflict,initial_status,parking_permitted in CASES:
        case=ASSIGNMENT+'__'+suffix
        config={'case_id':case,'selected_case_id':case,'supported_case_ids':[case],
                'candidate_id':'primary','law_id':'NRS-484B-410','cell_id':'C227853',
                'actor':'motor_vehicle_driver','approaching_conflict_requested':conflict,
                'requested_initial_status':initial_status,
                'requested_parking_permitted':parking_permitted,
                'initial_shoulder_y_m':-5.0,
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
                                    'Highway dedication, curb permission and initial status require sources',
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
                          'initial sourced status '+initial_status,
                          'sourced parking permission '+str(parking_permitted),
                          'no safety verdict or physical completion claim'],
            'status':'partial_native_execution_cpu_checked_physical_unverified'}
        path=HERE/'draft-departure'/suffix/'primary'/'construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(construction,indent=2)+'\n')
        fallback=copy.deepcopy(construction)
        fallback_config=copy.deepcopy(config)
        fallback_config['candidate_id']='fallback1'
        fallback_config['initial_shoulder_y_m']=-4.7
        for file in fallback['files']:
            if file['path']=='config.json':
                file['content']=json.dumps(fallback_config,indent=2)+'\n'
        fallback['mechanisms'].append('alternate shoulder spawn center -4.7 m')
        fallback_path=HERE/'draft-departure'/suffix/'fallback1'/'construction.json'
        fallback_path.parent.mkdir(parents=True,exist_ok=True)
        fallback_path.write_text(json.dumps(fallback,indent=2)+'\n')
        entries.append({'case_id':case,'kind':'delivery',
            'construction':str(path.relative_to(HERE)),
            'construction_sha256':sha(path),
            'candidate_risk':{'status':'physical',
                'reason':'Curb contact, merge trajectory and traffic clearance need Native review'},
            'candidates':[{'id':'fallback1',
                'construction':str(fallback_path.relative_to(HERE)),
                'construction_sha256':sha(fallback_path),
                'trigger':{'source':'original Native lane survey and spawn readback',
                           'metric':'initial shoulder actor center and lane projection',
                           'failure_condition':'primary -5.0 m shoulder spawn rejected or '
                                               'projects outside surveyed shoulder'},
                'changed_knobs':['initial shoulder center -5.0 m to -4.7 m']}],
            'delivery_readiness':'incomplete'})
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
