"""Build exact, unselected C110454 Native construction bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
NATIVE = HERE / 'native'
FILES = ('runner.py', 'geometry.py', 'controller.py', 'engineering.py',
         'cameras.py', 'measure.py', 'finalize.py')
TESTS = ('test_runner.py', 'test_bundle_engineering.py', 'test_bundle_measure.py',
         'test_bundle_finalize.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def description():
    names = ('drv.approaching', 'drv.in_intersection', 'st.intersection',
             'st.railway_crossing', 'st.centre_line', 'rel.occupies',
             'kin.position', 'rel.centre_distance', 'st.one_way_roadway',
             'native_body_pose_control', 'camera_frame_join')
    return {'channels': [{'name': name, 'unit': 'structured',
                         'sampling_rate_hz': 20,
                         'method': 'Original Native map, full body and synchronized video frame evidence; see runner and measure',
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
    runtime_manifest = sha(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    shared = [{'path': p, 'content': (NATIVE / p).read_text()} for p in FILES]
    shared += [{'path': 'tests/' + p, 'content': (NATIVE / p).read_text()} for p in TESTS]
    recording = description()
    manifest = {'format':'worker-unselected-draft-construction-manifest-v1',
                'assignment_id':ASSIGNMENT,
                'runtime_manifest_sha256':runtime_manifest,
                'status':'draft_not_selected', 'cases': []}
    proposal_cases = []
    engineering = json.loads((HERE / 'engineering-drafts.json').read_text())['plans']
    by_key = {(p['case'], p['candidate']):p for p in engineering}
    for suffix in ('reference', 'contrast'):
        case_id = ASSIGNMENT + '__' + suffix
        entry = {'case_id':case_id, 'kind':'draft_not_selected',
                 'candidate_risk':{'status':'physical',
                     'reason':'Native route tracking, parking stop and original camera framing require physical source checks'},
                 'measurement_contract':f'draft-candidates/{suffix}/measurement-contract.json',
                 'measurement_procedure':{'entrypoint':'finalize.py',
                                          'output_schema':'c110454-saved-analysis-v1'},
                 'candidates': []}
        if (HERE/f'update015-{suffix}-recipe.json').is_file():
            entry['fixture_recipe']=f'work/{ASSIGNMENT}/update015-{suffix}-recipe.json'
        proposal_cases.append({'case_id':case_id, 'target_law_id':'NRS-484B-213-2b',
                               'target_type':'attempt',
                               'recording_description':recording})
        write(HERE/'draft-candidates'/suffix/'measurement-contract.json',
              {'format':'worker-measurement-contract','case_id':case_id,
               'requirements':[
                 {'disposition_index':0,'requirement':'text-0',
                  'source':'inputs/coverage/branch-sources.json',
                  'output_key':'left_side_driving','method':'measure_left_side',
                  'value_type':'boolean','kind':'measured',
                  'inputs':['native_samples.jsonl','road_geometry.json']},
                 {'disposition_index':1,'requirement':'text-1',
                  'source':'inputs/coverage/branch-sources.json',
                  'output_key':'intersection_approach_relation',
                  'method':'measure_approach','value_type':'object','kind':'measured',
                  'inputs':['native_samples.jsonl','road_geometry.json']}],
               'negative':{'remove':['native_samples.jsonl'],
                           'error_contains':'Missing required source: native_samples.jsonl'}})
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            plan = by_key[suffix,candidate]
            config = {'case_id':case_id, 'selected_case_id':case_id,
                      'supported_case_ids':[case_id], 'case':{'case_id':case_id},
                      'case_suffix':suffix, 'candidate_id':candidate,
                      'cell_id':'C110454', 'law_id':'NRS-484B-213-2b',
                      'actor':'motor_vehicle_driver',
                      'duration_s':24, 'rate_hz':20,
                      'required_atoms':['st.intersection','st.centre_line',
                                        'rel.occupies','kin.position'],
                      'source_packets':[],
                      'mandatory_channels':[c['name'] for c in recording['channels']],
                      'recording_description':recording,
                      'cameras':[{'name':name,'width':width,'height':height}
                                 for name,width,height in
                                 [('overview',1920,1080),('approach',1280,720),
                                  ('reference_corner',1280,720),('driver_reference',1280,720)]],
                      'engineering_knobs':plan['knobs'],
                      'status':'unselected_native_runner_prototype'}
            files = shared + [{'path':'config.json',
                               'content':json.dumps(config, indent=2)+'\n'}]
            construction = {'case_id':case_id, 'cell_id':'C110454',
                            'law_id':'NRS-484B-213-2b',
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
                ref['trigger'] = plan['fallback_trigger'] | {
                    'failure_condition':
                    f"{plan['fallback_trigger']['metric']} {plan['fallback_trigger']['op']} "
                    f"{plan['fallback_trigger']['threshold']}"
                }
                ref['changed_knobs'] = [k for k, v in plan['knobs'].items()
                                        if v != by_key[suffix,'primary']['knobs'][k]]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE / 'draft-execution-manifest.json', manifest)
    write(HERE / 'proposals' / 'cases.json', {'cell_id':'C110454',
          'actor':'motor_vehicle_driver', 'status':'draft', 'cases':proposal_cases})
    print(json.dumps({'cases':len(manifest['cases']),
                      'candidates':sum(1+len(c['candidates']) for c in manifest['cases'])}))


if __name__ == '__main__':
    main()
