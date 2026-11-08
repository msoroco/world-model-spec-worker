"""Build exact, unselected C110454 exception bundles."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
NATIVE = HERE / 'native'
FILES = {'runner.py':'runner_exception.py', 'geometry.py':'geometry_exception.py',
         'controller.py':'controller.py', 'engineering.py':'engineering_exception.py', 'engineering_numeric.py':'engineering_numeric.py',
         'cameras.py':'cameras.py', 'measure_park.py':'measure_park.py',
         'finalize.py':'finalize_exception.py', 'exception_case.py':'exception_case.py', 'road.xodr':'road.xodr',
         'exception_evidence.py':'exception_evidence.py',
         'traffic_counterfactual.py':'traffic_counterfactual.py'}
TESTS = ('test_runner.py', 'test_bundle_proofs.py', 'test_bundle_finalize.py',
         'test_bundle_exception_evidence.py', 'test_bundle_exception_case.py')


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
                'status':'draft_not_selected', 'cases': [],
                'scope':'source-bound unselected exception alternatives; no physical or statutory outcome'}
    proposal_cases = []
    sys.path.insert(0,str(NATIVE))
    spec=importlib.util.spec_from_file_location('engineering_exception',NATIVE/'engineering_exception.py')
    engineering=importlib.util.module_from_spec(spec);spec.loader.exec_module(engineering)
    for suffix in engineering.CASES:
        case_id = ASSIGNMENT + '__' + suffix
        entry = {'case_id':case_id, 'kind':'draft_not_selected',
                 'candidate_risk':{'status':'physical',
                     'reason':'Native route tracking, parking stop and original camera framing require physical source checks'},
                 'measurement_contract':f'draft-exception-contracts/{suffix}/measurement-contract.json',
                 'measurement_procedure':{'entrypoint':'finalize.py',
                                          'output_schema':'c110454-lvmc-saved-analysis-v1'},
                 'candidates': []}
        proposal_cases.append({'case_id':case_id, 'target_law_id':'LVMC-11-52-130-A11',
                               'target_type':engineering.CASES[suffix][1],
                               'recording_description':recording})
        write(HERE/'draft-exception-contracts'/suffix/'measurement-contract.json',
              {'format':'unselected-exception-measurement-contract-v1',
               'case_id':case_id,'source':'LVMC 11.52.130(A)(11)',
               'output_key':'exception_source_context',
               'method':'inspect_case',
               'inputs':(['exception_context.json','other_actor_history.jsonl','ego_response_history.jsonl']
                         if suffix=='exception_1_2' else
                         ['exception_context.json','device_action_history.jsonl']
                         if suffix=='exception_2_2' else ['exception_context.json']),
               'negative':{'remove':['exception_context.json'],
                           'error_contains':'Missing required source: exception_context.json'},
               'exception_interpretation':'source packet completeness only; physical and statutory applicability require independent review'})
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
                      'exception_branch':plan['exception_branch'],
                      'requested_polarity':plan['requested_polarity'],
                      'mandatory_channels':[c['name'] for c in recording['channels']],
                      'recording_description':recording,
                      'cameras':[{'name':name,'width':width,'height':height}
                                 for name,width,height in
                                 [('overview',1920,1080),('approach',1280,720),
                                  ('intersection',1280,720),('parking',1280,720)]],
                      'engineering_knobs':plan['knobs'],
                      'status':'unselected_native_runner_prototype'}
            if suffix in ('exception_2_2','exception_3_2'):
                config.update(authored_device_source_id='620',physical_device_observed=False)
                variant_shared=[{'path':f['path'],'content':
                    (NATIVE/'runner_device.py').read_text() if f['path']=='runner.py' else
                    (NATIVE/'road_exception_device.xodr').read_text() if f['path']=='road.xodr' else f['content']}
                    for f in shared]
                variant_shared.append({'path':'tests/test_bundle_device_scene.py',
                    'content':(NATIVE/'test_bundle_device_scene.py').read_text()})
            else:
                variant_shared=shared
            files = variant_shared + [{'path':'config.json',
                               'content':json.dumps(config, indent=2)+'\n'}]
            construction = {'case_id':case_id, 'cell_id':'C110454',
                            'law_id':'LVMC-11-52-130-A11',
                            'actor':'motor_vehicle_driver',
                            'entrypoint':'runner.py', 'files':files,
                            'recording_description':recording,
                            'exception_scene':plan['scene'],
                            'exception_branch':plan['exception_branch'],
                            'requested_polarity':plan['requested_polarity'],
                            'measurement_plan':{'method':'saved original body, surveyed boundary and exception context source',
                                                'status':'unselected_cpu_proposal'},
                            'static_checks':['authored intersection and parking geometry',
                                             'statutory exception context source gate',
                                             'source-bound synthetic relation',
                                             'four-view 480-frame recording contract'],
                            'termination_rules':['full 480 original frames',
                                                 'capture or restoration failure retained'],
                            'mechanisms':['two-way intersection','observed-pose route controller',
                                          plan['scene']['control'],
                                          'four synchronized lossless cameras'],
                            'status':'unselected_cpu_draft'}
            if suffix in ('exception_2_2','exception_3_2'):
                construction['authored_device_asset']='road.xodr signal 620; Native map readback required'
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
    write(HERE / 'draft-exception-execution-manifest.json', manifest)
    proposal_path=HERE/'proposals'/'cases.json'
    existing=json.loads(proposal_path.read_text())
    existing['cases']=[c for c in existing['cases'] if c['case_id'] not in
                       {p['case_id'] for p in proposal_cases}]+proposal_cases
    write(proposal_path,existing)
    print(json.dumps({'cases':len(manifest['cases']),
                      'candidates':sum(1+len(c['candidates']) for c in manifest['cases'])}))


if __name__ == '__main__':
    main()
