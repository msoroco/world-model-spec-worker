"""Build the two selected rider-count cases and distinct spawn-recovery candidates."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-777-3'
ACTOR = 'cycle_or_scooter_operator'
CASES = [AID + '__controlled_1', AID + '__controlled_2']
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def recording():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    terms = [row['term'] for row in assignment['source_observation_terms']]
    names = list(dict.fromkeys([*terms, 'rider_identity', 'rider_pose',
                                 'camera_frame_join', 'roadway_and_exception_review']))
    return {'channels': [{'name': name, 'unit': 'structured',
             'method': '600 original Native rider poses, roadway review and four-camera source join',
             'sampling_rate_hz': 20, 'time_window': '30 s / 600 original frames',
             'reference_frame': 'original Native map and frame',
             'uncertainty': 'Bicycle classification, roadway and exclusive-use legal review pending'}
             for name in names],
            'context_inputs': [{'name': 'roadway_exception_context', 'unit': 'structured',
             'method': 'Original public-road, shoulder, device and exclusive-use source review'}],
            'limitations': ['Longitudinal footprint overlap and lateral bearing are measurements, not a legal abreast cutoff.',
                            'Synthetic CPU fixtures cannot prove original physical riding or legal status.']}


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    desc = recording()
    proposals = []
    rows = []
    for index, case_id in enumerate(CASES):
        label = case_id.rsplit('__', 1)[-1]
        rider_count = index + 2
        proposal = {'case_id': case_id, 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Compare measured simultaneous rider geometry on a reviewed roadway while preserving the exclusive-use exception for source review.',
            'variable_assignments': {
                'requested_rider_count': {'kind': 'controller', 'unit': 'count', 'value': rider_count},
                'route_and_device_class': {'kind': 'world_setup', 'unit': 'categorical',
                 'value': 'same reviewed public roadway, qualifying bicycles and exclusive-use survey'}},
            'paired_probe_id': AID + '__abreast_pair',
            'deliberate_differences': ['requested_rider_count'],
            'probe': {'primary_variable': 'requested_rider_count',
                      'comparison_or_standard': 'source-joined longitudinal overlap and lateral bearing; no legal cutoff inferred',
                      'target_value_or_branch': rider_count},
            'unresolved_judgment_calls': ['more than two abreast',
                                           'upon a roadway', 'exclusive-use path or roadway part'],
            'recording_description': desc}
        proposals.append(proposal)
        entry = {'case_id': case_id, 'kind': 'delivery', 'id': 'primary',
            'candidate_risk': {'status': 'physical',
             'reason': 'Multiple bicycle/rider actor spawns can fail or their original longitudinal and lateral geometry can diverge.'},
            'candidates': [], 'measurement_contract': f'measurement-{label}.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c230328-abreast-saved-analysis-v1'},
            'fixture_recipe': f'work/{AID}/diagnostic-{label}-primary-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {channel['name']: {'entrypoint': 'finalize.py',
             'method': 'original rider/device pose, roadway/exception and four-camera source join',
             'evidence': 'Synthetic diagnostic only; original physical and legal review pending'}
             for channel in desc['channels']}}
        source = FOLDER / ('native' if index == 0 else 'native/controlled_2')
        for candidate, shift in (('primary', 0.0), ('fallback1', .18)):
            cfg = json.loads((source / 'config.json').read_text())
            cfg['candidate_id'] = candidate
            cfg['spawn_shift_y_m'] = shift
            cfg['recording_description'] = desc
            cfg['physical_completion'] = {'criterion': 'travel_progress',
             'motion_source': 'trace.jsonl', 'position_key': 'position_m',
             'minimum_progress_m': 10, 'engineering_tolerances_not_legal': True}
            files = [{'path': name, 'source': f'work/{AID}/{(source/name).relative_to(FOLDER)}',
                      'content': (source / name).read_text()}
                     for name in ('runner.py', 'tests/test_native.py')]
            for name in ('measure_abreast.py', 'finalize.py'):
                path = FOLDER / (name if name == 'measure_abreast.py' else 'native/' + name)
                if path.exists():
                    files.append({'path': name, 'source': f'work/{AID}/{path.relative_to(FOLDER)}',
                                  'content': path.read_text()})
            files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'})
            construction = {'case_id': case_id, 'cell_id': 'C230328', 'law_id': LAW,
              'actor': ACTOR, 'entrypoint': 'runner.py', 'files': files,
              'recording_description': desc, 'status': 'selected_cpu_construction',
              'measurement_plan': 'Saved original rider intervals, lateral bearings, roadway and exclusive-use review; legal judgment unresolved.',
              'static_checks': ['source-hashed rider identities and camera construction',
                                '600 original frame source join'],
              'termination_rules': ['600 original frames at 20 Hz',
                                    'reject source gaps and restore owned world'],
              'mechanisms': ['Native bicycle and rider actors', 'roadway and exclusive-use review',
                             'source-joined saved geometry and independent review']}
            path = FOLDER / 'native/selected-drafts' / label / candidate / 'construction.json'
            write(path, construction)
            binding = {'construction': str(path.relative_to(FOLDER)),
                       'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(binding)
            else:
                entry['candidates'].append({'id': candidate, **binding,
                 'trigger': {'source': 'native-capture-report.json',
                             'metric': 'rider_spawn_and_abreast_geometry',
                             'failure_condition': 'actor spawn failed or intended original rider geometry absent'},
                 'changed_knobs': ['spawn_shift_y_m +0.18 m']})
        rows.append(entry)
        dispositions = plan['requirement_dispositions']
        specifications = (('roadway_riding', 'measure_roadway_riding',
                           ['rider_poses.jsonl', 'road_context.json']),
                          ('exclusive_use_exception', 'measure_exclusive_use_exception',
                           ['rider_poses.jsonl', 'road_context.json']))
        requirements = [{'disposition_index': i, 'requirement': d['requirement'],
                         'source': d['source'], 'output_key': key, 'method': method,
                         'value_type': 'object', 'kind': 'measured', 'inputs': sources}
                        for i, (d, (key, method, sources)) in enumerate(zip(dispositions, specifications))]
        write(FOLDER / f'measurement-{label}.json',
              {'format': 'worker-measurement-contract', 'requirements': requirements,
               'negative': {'remove': ['rider_poses.jsonl'],
                            'error_contains': 'Missing required source: rider_poses.jsonl'}})
    write(FOLDER / 'proposals/cases.json',
          {'format': 'worker-case-proposals', 'cell_id': 'C230328', 'actor': ACTOR,
           'law_id': LAW, 'status': 'draft', 'cases': proposals,
           'sweep_specs': [], 'sweeps_expanded': True})
    write(FOLDER / 'execution-manifest.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
           'status': 'selected_cpu_construction_partial', 'cases': rows})
    print(json.dumps({'cases': CASES,
                      'manifest_sha256': sha(FOLDER / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
