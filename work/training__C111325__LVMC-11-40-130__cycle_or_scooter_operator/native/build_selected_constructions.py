"""Bind selected bicycle cases and physical fallback to current package code."""
import hashlib
import json
from pathlib import Path
from bicycle_setup import plan

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Returned file too large')


def build():
    proposal = json.loads((FOLDER/'proposals/cases.json').read_text())
    plan_source = json.loads((FOLDER/'case-plan.json').read_text())
    entries = []
    for condition in ('condition_a', 'condition_b'):
        case_id = next(case['case_id'] for case in proposal['cases']
                       if case['case_id'].endswith(condition))
        description = next(case['recording_description'] for case in proposal['cases']
                           if case['case_id'] == case_id)
        choices = []
        for candidate in ('primary', 'fallback1'):
            request = plan(condition, candidate)
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'supported_case_ids': [case_id],
                      'cell_id': 'C111325', 'law_id': 'LVMC-11-40-130',
                      'actor': 'cycle_or_scooter_operator',
                      'condition': condition, 'candidate_id': candidate,
                      'requested_speed_mps': request['requested_peak_speed_mps'],
                      'start_xyz_m': list(request['start_xyz_m']),
                      'rate_hz': 20, 'duration_s': 30,
                      'cameras': [{k: item[k] for k in ('name','width','height')}
                                  for item in request['cameras']],
                      'required_atoms': [], 'source_packets': [],
                      'case': {'case_id': case_id},
                      'recording_description': description,
                      'physical_completion': {'criterion': 'travel_progress',
                                              'motion_source': 'trace.jsonl',
                                              'minimum_progress_m': 10,
                                              'engineering_tolerances_not_legal': True}}
            files = [{'path': name, 'content': (HERE/name).read_text()}
                     for name in ('runner.py','live_capture.py','bicycle_setup.py',
                                  'bicycle_control.py','survey.py','build_speed_road.py',
                                  'audit_original_speed.py','finalize.py','road.xodr')]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'})
            files.append({'path': 'tests/test_exact.py', 'content':
                'import json\nfrom runner import check\n\ndef test_exact_case():\n    assert check()["passed"] is True\n'})
            construction = {'case_id': case_id, 'cell_id': 'C111325',
                            'law_id': 'LVMC-11-40-130',
                            'actor': 'cycle_or_scooter_operator',
                            'entrypoint': 'runner.py', 'files': files,
                            'recording_description': description,
                            'status': 'selected_cpu_construction',
                            'measurement_plan': 'Original bicycle pose/velocity, route survey and 600 joined source frames; prudence unresolved.'}
            target = HERE/'selected-drafts'/condition/candidate/'construction.json'
            write(target, construction)
            choices.append({'id': candidate,
                            'construction': str(target.relative_to(FOLDER)),
                            'construction_sha256': sha(target)})
        entries.append({'case_id': case_id,
                        'construction': choices[0]['construction'],
                        'construction_sha256': choices[0]['construction_sha256'],
                        'candidates': [{**choices[1],
                                        'trigger': {'source': 'native-capture-report.json',
                                                    'metric': 'bicycle_spawn_and_approach',
                                                    'failure_condition': 'spawn failed or stop-sign approach missing'},
                                        'changed_knobs': ['bicycle_start_x_m -2 m']}],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Bicycle spawn may overlap local map or miss the intended sign approach.'},
                        'kind': 'delivery', 'id': 'primary',
                        'measurement_contract': 'measurement-'+condition+'.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py',
                                                  'output_schema': 'c111325-bicycle-speed-saved-analysis-v1'},
                        'fixture_recipe': str((FOLDER/('diagnostic-'+condition+'-recipe.json')).relative_to(REPO)),
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'acquisition': {name: {'entrypoint': 'finalize.py',
                                               'method': 'original bicycle readback, survey, and saved frame join',
                                               'evidence': 'Synthetic diagnostic only; original Native physical review pending'}
                                        for name in [item['name'] for item in description['channels']]}})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [
                        {'disposition_index': 0,
                         'requirement': plan_source['requirement_dispositions'][0]['requirement'],
                         'source': plan_source['requirement_dispositions'][0]['source'],
                         'output_key': 'bicycle_speed_conditions',
                         'method': 'measure_bicycle_speed', 'value_type': 'object',
                         'kind': 'measured',
                         'inputs': ['native-bicycle-trace.jsonl','context.json']},
                        {'disposition_index': 1,
                         'requirement': plan_source['requirement_dispositions'][1]['requirement'],
                         'source': plan_source['requirement_dispositions'][1]['source'],
                         'output_key': 'stop_approach_scope',
                         'method': 'measure_stop_approach', 'value_type': 'object',
                         'kind': 'measured',
                         'inputs': ['native-bicycle-trace.jsonl','context.json','video_frames.jsonl']}],
                    'negative': {'remove': ['native-bicycle-trace.jsonl'],
                                 'error_contains': 'Missing required source: native-bicycle-trace.jsonl'}}
        write(FOLDER/('measurement-'+condition+'.json'), contract)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': FOLDER.name,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_cpu_construction_partial', 'cases': entries}
    write(FOLDER/'execution-manifest.json', manifest)
    return {'selected_cases': len(entries), 'candidate_constructions': 4,
            'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}


if __name__ == '__main__':
    print(json.dumps(build()))
