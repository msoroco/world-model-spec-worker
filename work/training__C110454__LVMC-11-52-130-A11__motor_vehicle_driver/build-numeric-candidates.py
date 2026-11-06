"""Build exact, unselected C110454 numeric parking-boundary bundles."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
NATIVE = HERE / 'native'
FILES = {'runner.py':'runner.py', 'geometry.py':'geometry.py',
         'controller.py':'controller.py', 'engineering.py':'engineering_numeric.py',
         'cameras.py':'cameras.py', 'measure_park.py':'measure_park.py',
         'finalize.py':'finalize_numeric.py', 'road.xodr':'road.xodr',
         'exception_evidence.py':'exception_evidence.py'}
TESTS = ('test_runner.py', 'test_bundle_proofs.py', 'test_bundle_finalize.py',
         'test_bundle_exception_evidence.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def description():
    names = ('drv.standing_or_parked', 'st.intersection',
             'rel.centre_distance', 'rel.occupies', 'kin.extent',
             'native_body_pose_control', 'camera_frame_join')
    return {'channels': [{'name': name, 'unit': 'structured',
                         'sampling_rate_hz': 20,
                         'method': 'Original Native map, resting full body and synchronized video frame evidence; see runner and measure_park',
                         'time_window': 'original 24 s / 480 frame attempt',
                         'reference_frame': 'surveyed Native map and original frame',
                         'uncertainty': '50 ms samples; physical map and pixels require actual capture'}
                        for name in names],
            'context_inputs': [{'name':'surveyed_two_way_intersection',
                                'unit':'structured',
                                'method':'Native OpenDRIVE readback and lane direction survey'}],
            'limitations': ['CPU fixture does not establish physical behavior or legal verdict']}


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    runtime_manifest = batch['runtime']['source_manifest_sha256']
    shared = [{'path': p, 'content': (NATIVE / source).read_text()}
              for p,source in FILES.items()]
    shared += [{'path': 'tests/' + p, 'content': (NATIVE / p).read_text()} for p in TESTS]
    recording = description()
    manifest = {'format':'worker-unselected-draft-construction-manifest-v1',
                'assignment_id':ASSIGNMENT,
                'runtime_manifest_sha256':runtime_manifest,
                'status':'draft_not_selected', 'cases': []}
    proposal_cases = []
    spec=importlib.util.spec_from_file_location('engineering_numeric',NATIVE/'engineering_numeric.py')
    engineering=importlib.util.module_from_spec(spec);spec.loader.exec_module(engineering)
    for suffix in engineering.CASES:
        case_id = ASSIGNMENT + '__' + suffix
        entry = {'case_id':case_id, 'kind':'draft_not_selected',
                 'candidate_risk':{'status':'physical',
                     'reason':'Native route tracking, parking stop and original camera framing require physical source checks'},
                 'measurement_contract':f'draft-numeric-contracts/{suffix}/measurement-contract.json',
                 'measurement_procedure':{'entrypoint':'finalize.py',
                                          'output_schema':'c110454-lvmc-saved-analysis-v1'},
                 'candidates': []}
        proposal_cases.append({'case_id':case_id, 'target_law_id':'LVMC-11-52-130-A11',
                               'target_type':{'numeric_1_0':'below','numeric_1_1':'at',
                                              'numeric_1_2':'above'}[suffix],
                               'recording_description':recording})
        write(HERE/'draft-numeric-contracts'/suffix/'measurement-contract.json',
              {'format':'unselected-numeric-measurement-contract-v1',
               'case_id':case_id,'source':'LVMC 11.52.130(A)(11)',
               'output_key':'parked_body_distance_and_rest_interval',
               'method':'measure_case_sources',
               'inputs':['native_parking_history.json'],
               'negative':{'remove':['native_parking_history.json'],
                           'error_contains':'Missing required source: native_parking_history.json'},
               'boundary_interpretation':'exact value unresolved within 0.05 m sampling/geometry guard'})
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            plan = engineering.plan(suffix,candidate)
            config = {'case_id':case_id, 'selected_case_id':case_id,
                      'supported_case_ids':[case_id], 'case':{'case_id':case_id},
                      'case_suffix':suffix, 'candidate_id':candidate,
                      'cell_id':'C110454', 'law_id':'LVMC-11-52-130-A11',
                      'actor':'motor_vehicle_driver',
                      'duration_s':24, 'rate_hz':20,
                      'required_atoms':['st.intersection','rel.centre_distance',
                                        'rel.occupies','kin.extent'],
                      'source_packets':[],
                      'mandatory_channels':[c['name'] for c in recording['channels']],
                      'recording_description':recording,
                      'cameras':[{'name':name,'width':width,'height':height}
                                 for name,width,height in
                                 [('overview',1920,1080),('approach',1280,720),
                                  ('intersection',1280,720),('parking',1280,720)]],
                      'engineering_knobs':plan['knobs'],
                      'status':'unselected_native_runner_prototype'}
            files = shared + [{'path':'config.json',
                               'content':json.dumps(config, indent=2)+'\n'}]
            construction = {'case_id':case_id, 'cell_id':'C110454',
                            'law_id':'LVMC-11-52-130-A11',
                            'actor':'motor_vehicle_driver',
                            'entrypoint':'runner.py', 'files':files,
                            'recording_description':recording,
                            'measurement_plan':{'method':'saved original body and surveyed boundary distance',
                                                'status':'unselected_cpu_proposal'},
                            'static_checks':['authored intersection and parking geometry',
                                             'source-bound synthetic relation',
                                             'four-view 480-frame recording contract'],
                            'termination_rules':['full 480 original frames',
                                                 'capture or restoration failure retained'],
                            'mechanisms':['two-way intersection','observed-pose route controller',
                                          'four synchronized lossless cameras'],
                            'status':'unselected_cpu_draft'}
            path = HERE / 'draft-candidates' / suffix / candidate / 'construction.json'
            write(path, construction)
            ref = {'id':candidate,
                   'construction':str(path.relative_to(HERE)),
                   'construction_sha256':sha(path)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                metric,op,threshold=plan['measured_trigger']
                ref['trigger']={'source':'original Native pose and decoded source video',
                    'metric':metric,'op':op,'threshold':threshold,
                    'failure_condition':f'{metric} {op} {threshold}'}
                ref['changed_knobs'] = [k for k, v in plan['knobs'].items()
                                        if v != engineering.plan(suffix,'primary')['knobs'][k]]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE / 'draft-numeric-execution-manifest.json', manifest)
    proposal_path=HERE/'proposals'/'cases.json'
    existing=json.loads(proposal_path.read_text())
    existing['cases']=[c for c in existing['cases'] if c['case_id'] not in
                       {p['case_id'] for p in proposal_cases}]+proposal_cases
    write(proposal_path,existing)
    print(json.dumps({'cases':len(manifest['cases']),
                      'candidates':sum(1+len(c['candidates']) for c in manifest['cases'])}))


if __name__ == '__main__':
    main()
