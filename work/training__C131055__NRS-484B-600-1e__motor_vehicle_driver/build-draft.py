"""Bundle exact roundabout-exit CPU Native draft for pinned offline check."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__controlled_2'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    config={'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],
            'candidate_id':'primary','law_id':'NRS-484B-600-1e','cell_id':'C131055',
            'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,
            'required_atoms':[],'source_packets':[],'case':{'case_id':CASE},
            'cameras':[{'name':name,'width':1280,'height':720} for name in
                ('roundabout_overview','arc_entry','exit_tangent','subject_chase')],
            'recording_description':{'channels':[{'name':'original_vehicle_velocity_position',
                'unit':'structured','sampling_rate_hz':20,
                'method':'Native post-tick actor transform, velocity and lane readback',
                'time_window':'600 frames','reference_frame':'surveyed roundabout arc and east exit',
                'uncertainty':'50 ms sampling'}],
                'limitations':['Controller target speed is not measured speed',
                               'Roundabout-to-exit traversal and original pixels require Native review']},
            'status':'partial_cpu_draft'}
    files=[{'path':name,'content':(HERE/'native'/name).read_text()}
           for name in ('runner.py','geometry.py','measure.py','tests/test_native.py')]
    files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
    proposal={'case_id':CASE,'law_id':config['law_id'],'cell_id':config['cell_id'],
              'actor':config['actor'],'entrypoint':'runner.py','files':files,
              'recording_description':config['recording_description'],
              'measurement_plan':{'entrypoint':'measure.py',
                  'required_sources':['roundabout-speed-history.jsonl','roundabout-survey.json'],
                  'status':'source_bound_cpu_draft'},
              'static_checks':['two-lane 500m-radius roundabout arc joined to two-lane east exit',
                               'four synchronized cameras and 600 Native frames'],
              'termination_rules':['600 original frames','destroy owned actors and restore prior world'],
              'mechanisms':['measured post-tick speed on arc and exit',
                            'controller requests below or above 80 mph without claiming achieved speed'],
              'status':'partial_native_execution_cpu_checked_physical_unverified'}
    path=HERE/'draft-roundabout/above_80_request/primary/construction.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(proposal,indent=2)+'\n')
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':HERE.name,
              'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
              'status':'partial','cases':[{'case_id':CASE,'kind':'delivery',
                  'construction':str(path.relative_to(HERE)),'construction_sha256':sha(path),
                  'candidate_risk':{'status':'physical','reason':'High-speed arc/exit lane retention and speed achievement require Native review'},
                  'candidates':[],'measurement_procedure':{'entrypoint':'measure.py'},
                  'delivery_readiness':'incomplete'}]}
    (HERE/'draft-roundabout-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'case_id':CASE,'construction_sha256':sha(path),
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))
if __name__=='__main__':main()
