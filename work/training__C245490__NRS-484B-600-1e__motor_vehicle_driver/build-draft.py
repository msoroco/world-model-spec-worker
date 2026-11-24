"""Build CPU Native lane-change speed draft on pinned runtime."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__probe_03'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    config={'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],
        'candidate_id':'primary','law_id':'NRS-484B-600-1e','cell_id':'C245490',
        'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,
        'required_atoms':[],'source_packets':[],'case':{'case_id':CASE},
        'cameras':[{'name':name,'width':1280,'height':720} for name in
            ('overview','lane_change','road_ahead','subject_chase')],
        'recording_description':{'channels':[
            {'name':'original_velocity','unit':'m/s vector','sampling_rate_hz':20,
             'method':'Native actor velocity post-tick','time_window':'600 frames',
             'reference_frame':'world','uncertainty':'50 ms sampling'},
            {'name':'original_lane','unit':'lane ID','sampling_rate_hz':20,
             'method':'Native waypoint post-tick','time_window':'600 frames',
             'reference_frame':'OpenDRIVE road 1','uncertainty':'map projection'}],
            'limitations':['Accepted membership lacks source-hashed equivalence review',
                           'High-speed capability and lane-change trajectory not physically verified']},
        'status':'partial_cpu_draft'}
    files=[{'path':name,'content':(HERE/'native'/name).read_text()}
        for name in ('runner.py','geometry.py','measure.py','tests/test_native.py')]
    files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
    proposal={'case_id':CASE,'law_id':config['law_id'],'cell_id':config['cell_id'],
        'actor':config['actor'],'entrypoint':'runner.py','files':files,
        'recording_description':config['recording_description'],
        'measurement_plan':{'entrypoint':'measure.py',
            'required_sources':['speed-lane-history.jsonl','lane-survey.json'],
            'status':'source_bound_cpu_draft'},
        'static_checks':['1700m same-direction two-lane OpenDRIVE','four original cameras',
                         '600 frames at 20Hz','original velocity and lane readback'],
        'termination_rules':['600 original frames','restore world and destroy owned actors'],
        'mechanisms':['requested 36.5m/s with smooth lateral-velocity lane transition',
                      'record actual velocity and lane IDs; never infer requested speed as achieved'],
        'status':'partial_native_execution_cpu_checked_physical_unverified'}
    path=HERE/'draft-speed/above_80_lane_change/primary/construction.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(proposal,indent=2)+'\n')
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':HERE.name,
        'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
        'status':'partial','cases':[{'case_id':CASE,'kind':'delivery',
            'construction':str(path.relative_to(HERE)),'construction_sha256':sha(path),
            'candidate_risk':{'status':'physical',
                'reason':'Actual speed and lane transition may fail at high-speed request'},
            'candidates':[],'measurement_procedure':{'entrypoint':'measure.py'},
            'delivery_readiness':'incomplete'}]}
    (HERE/'draft-speed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'case_id':CASE,'construction_sha256':sha(path),
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))

if __name__=='__main__':main()
