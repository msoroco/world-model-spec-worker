"""Build source-bound exact C183370 candidate bundles for offline proof."""
import hashlib
import json
from pathlib import Path

from capture import CAMERAS
from bundle_runner import KNOBS
from recording_contract import ASSIGNMENT, config as recording_config

PACKAGE=Path(__file__).resolve().parents[1]
NATIVE=PACKAGE/'native'
MODULES=('pathing.py','scene_plan.py','live_readback.py','route_control.py',
         'recording_contract.py','capture.py','analyze.py','finalize.py',
         'review_annotations.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_file(path, source):
    return {'path':path,'content':source.read_text(),
            'source':'work/'+ASSIGNMENT+'/native/'+source.name}


FALLBACKS = {
    'fallback1': {
        'trigger': {'source':'native-actors.jsonl',
                    'metric':'observed speed/route tracking at surveyed pavement',
                    'failure_condition':'ego overshoots the surveyed route while slowing for the protected region'},
        'changed_knobs':['lower requested controller speed from 4 to 3 m/s']},
    'fallback2': {
        'trigger': {'source':'overview.mkv',
                    'metric':'visibility of warning person and complete surveyed pavement area',
                    'failure_condition':'overview pixels omit the person or a protected pavement edge'},
        'changed_knobs':['raise overview camera from 24 to 28 m and pitch from -55 to -62 degrees']},
    'fallback3': {
        'trigger': {'source':'native-actors.jsonl',
                    'metric':'measured lateral route error at pavement approach',
                    'failure_condition':'body footprint leaves the surveyed intended route corridor'},
        'changed_knobs':['reduce waypoint reach from 1.5 to 1.0 m',
                         'increase steering response by reducing divisor from 40 to 32 degrees']},
}


def build(case, candidate='primary'):
    if case not in ('reference','contrast'):
        raise ValueError('Unknown C183370 exact case')
    if candidate not in KNOBS:
        raise ValueError('Unknown C183370 candidate')
    cfg=recording_config(case,600)
    cfg.update(assignment_id=ASSIGNMENT,selected_case_id=cfg['case_id'],
               frames=600,required_atoms=[],source_packets=[],
               original_native_observed=False,
               physical_success_claimed=False,
               cameras=[{'name':name,'width':width,'height':height,
                         'fov_deg':fov,'pose_strategy':'ego_attached'}
                        for name,width,height,fov,*_ in CAMERAS])
    controls,cameras=KNOBS[candidate]
    cfg.update(candidate_id=candidate,controller_knobs=controls,
               camera_overrides=cameras)
    files=[source_file('runner.py',NATIVE/'bundle_runner.py'),
           source_file('tests/test_bundle.py',NATIVE/'offline_bundle_test.py')]
    files.extend(source_file('native/'+name,NATIVE/name) for name in MODULES)
    files.append({'path':'config.json','content':json.dumps(cfg,indent=2,sort_keys=True)+'\n'})
    return {'case_id':cfg['case_id'],'law_id':'LVMC-11-22-100',
            'cell_id':'C183370','actor':'motor_vehicle_driver',
            'entrypoint':'runner.py','files':files,
            'status':'draft_exact_candidate_cpu_offline',
            'original_native_observed':False,'delivery_ready':False,
            'recording_description':cfg['recording_description'],
            'measurement_plan':{'selected_variable':'drive_over_warned_new_pavement',
                'requested_footprint_contact':case=='reference',
                'source':'original actor body vertices and surveyed pavement polygon',
                'warning_and_repair':'independent camera source review required',
                'employee_exception':'independent source review required'},
            'static_checks':['runner.py --check','tests/test_bundle.py'],
            'termination_rules':{'frames':600,'capture_rate_hz':20},
            'mechanisms':{'scene':'source-surveyed live CARLA map and warning person',
                          'control':'native/route_control.py',
                          'capture':'native/capture.py',
                          'finalization':'native/finalize.py'}}


def write():
    cases=[]
    target=PACKAGE/'draft-exact-candidates'
    for case in ('reference','contrast'):
        variants={}
        for candidate in KNOBS:
            folder=target/case/candidate
            folder.mkdir(parents=True,exist_ok=True)
            path=folder/'construction.json'
            path.write_text(json.dumps(build(case,candidate),indent=2,sort_keys=True)+'\n')
            variants[candidate]={'construction':str(path.relative_to(PACKAGE)),
                                 'construction_sha256':sha(path)}
        candidates=[dict(id=candidate,**variants[candidate],**FALLBACKS[candidate])
                    for candidate in FALLBACKS]
        cases.append({'case_id':ASSIGNMENT+'__'+case,'kind':'delivery',
                      **variants['primary'],
                      'candidate_risk':{'status':'physical',
                          'reason':'Native body tracking and warning/pavement camera visibility remain unverified'},
                      'candidates':candidates,
                      'candidate_offline_status':'pending'})
    runtime=PACKAGE.parents[1]/'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest={'format':'worker-execution-manifest',
              'assignment_id':ASSIGNMENT,
              'status':'draft_exact_candidates_not_delivery_ready',
              'runtime_manifest_sha256':sha(runtime),
              'source_branch':'warning_person',
              'cases':cases}
    path=PACKAGE/'draft-exact-candidate-manifest.json'
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return path


if __name__=='__main__':
    print(write())
