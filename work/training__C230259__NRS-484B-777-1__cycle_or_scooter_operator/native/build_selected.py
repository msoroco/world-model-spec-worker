"""Build exact current-runtime reference/contrast primary and risk fallback bundles."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-777-1'
ACTOR = 'cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
IDS = [AID + '__reference', AID + '__contrast']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def recording():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    terms = [row['term'] for row in assignment['source_observation_terms']]
    names = list(dict.fromkeys([*terms, 'ego_pose', 'ego_speed',
                                'cycle_lateral_distance_from_right_edge',
                                'standing_vehicle_clearance', 'camera_frame_join']))
    return {'channels': [{'name': name, 'unit': 'structured',
                          'method': 'Original 600-frame bicycle, standing-vehicle, road-edge and four-camera source join',
                          'sampling_rate_hz': 20, 'time_window': '30 s / 600 original frames',
                          'reference_frame': 'original Native map and frame',
                          'uncertainty': 'Original physical appearance and qualitative legal review pending'}
                         for name in names],
            'context_inputs': [{'name': 'right_edge_pass_context', 'unit': 'structured',
                                'method': 'Original roadway width, standing object, nearby traffic and turn intent survey'}],
            'limitations': ['Neither a lateral margin nor standing-vehicle clearance is a legal practicability or due-care threshold.',
                            'Synthetic CPU fixtures do not prove original rider identity, physical passing or camera pixels.']}


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    desc = recording()
    proposals = []
    for case_id, y in zip(IDS, (-2.65, -1.45)):
        proposals.append({'case_id': case_id, 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Measure bicycle right-edge position and standing-vehicle passing clearance; preserve qualitative exceptions and due care for review.',
            'variable_assignments': {
                'requested_cycle_center_y_m': {'kind': 'controller', 'unit': 'm', 'value': y},
                'route_and_standing_vehicle': {'kind': 'world_setup', 'unit': 'categorical',
                    'value': 'same authored right-edge road, standing vehicle, weather and absent nearby traffic/turn'}},
            'paired_probe_id': AID + '__right_edge_pair',
            'deliberate_differences': ['requested_cycle_center_y_m'],
            'probe': {'primary_variable': 'requested_cycle_center_y_m',
                      'comparison_or_standard': 'measured body-to-edge and passing-clearance contrast, not legal threshold',
                      'target_value_or_branch': y},
            'unresolved_judgment_calls': ['as near to the right side of the roadway as practicable',
                                          'exercising due care when passing a standing vehicle',
                                          'When doing so would not be safe'],
            'recording_description': desc})
    proposal = {'format': 'worker-case-proposals', 'cell_id': 'C230259', 'actor': ACTOR,
                'law_id': LAW, 'status': 'draft', 'cases': proposals, 'sweep_specs': [],
                'sweeps_expanded': True}
    write(FOLDER / 'proposals/cases.json', proposal)
    rows = []
    native_files = ('runner.py', 'capture.py', 'geometry.py', 'measure_right_edge.py',
                    'measurement-contract.json', 'finalize.py', 'prove_right_edge.py', 'tests/test_saved.py')
    for case_id, y in zip(IDS, (-2.65, -1.45)):
        label = case_id.rsplit('__', 1)[-1]
        entry = {'case_id': case_id, 'kind': 'delivery', 'id': 'primary',
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Bicycle spawn can overlap the shoulder or standing vehicle and fail the intended passing geometry.'},
                 'candidates': [], 'measurement_contract': f'measurement-{label}.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c230259-right-edge-saved-analysis-v1'},
                 'fixture_recipe': f'work/{AID}/diagnostic-{label}-primary-recipe.json',
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                 'acquisition': {name: {'entrypoint': 'finalize.py',
                    'method': 'original bicycle/standing actor and right-roadway-edge source join',
                    'evidence': 'Synthetic diagnostic only; original physical review pending'}
                    for name in [c['name'] for c in desc['channels']]}}
        for candidate, offset in (('primary', 0), ('fallback1', .15 if label == 'reference' else -.15)):
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'supported_case_ids': IDS, 'candidate_id': candidate,
                      'law_id': LAW, 'cell_id': 'C230259', 'actor': ACTOR,
                      'rider_class': 'bicycle', 'condition': label,
                      'rate_hz': 20, 'duration_s': 30,
                      'required_atoms': [], 'source_packets': [],
                      'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                                   'height': 1080 if name == 'overview' else 720,
                                   'pose_strategy': 'surveyed bicycle and standing-vehicle passing interval',
                                   'fov_deg': 85} for name in VIEWS],
                      'requested_cycle_center_y_m': y + offset,
                      'case': proposals[IDS.index(case_id)],
                      'recording_description': desc,
                      'physical_completion': {'criterion': 'travel_progress',
                                               'motion_source': 'trace.jsonl',
                                               'position_key': 'position_m',
                                               'minimum_progress_m': 10,
                                               'engineering_tolerances_not_legal': True}}
            files = [{'path': name, 'source': f'work/{AID}/native/{name}',
                      'content': (FOLDER / 'native' / name).read_text()} for name in native_files]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
            construction = {'case_id': case_id, 'cell_id': 'C230259', 'law_id': LAW,
                            'actor': ACTOR, 'entrypoint': 'runner.py', 'files': files,
                            'recording_description': desc, 'status': 'selected_cpu_construction',
                            'measurement_plan': 'Saved original actor footprints, roadway edge, exception context and four synchronized cameras; legal judgment unresolved.',
                            'static_checks': ['source-hashed map, actor and camera construction', '600 original frame source join'],
                            'termination_rules': ['600 original frames at 20 Hz', 'reject source gaps and restore owned world'],
                            'mechanisms': ['Native bicycle and standing vehicle', 'roadway edge readback',
                                           'source-joined saved measurement and independent review']}
            path = FOLDER / 'native/selected-drafts' / label / candidate / 'construction.json'
            write(path, construction)
            binding = {'construction': str(path.relative_to(FOLDER)), 'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(binding)
            else:
                entry['candidates'].append({'id': 'fallback1', **binding,
                    'trigger': {'source': 'native-capture-report.json',
                                'metric': 'bicycle_spawn_and_standing_pass',
                                'failure_condition': 'spawn failed or standing-vehicle passing interval absent'},
                    'changed_knobs': ['requested_cycle_center_y_m ' + ('+0.15' if offset > 0 else '-0.15') + ' m']})
        rows.append(entry)
        requirements = [{'disposition_index': i, 'requirement': d['requirement'],
                         'source': d['source'], 'output_key': key,
                         'method': method, 'value_type': 'object', 'kind': 'measured',
                         'inputs': sources}
                        for i, (d, (key, method, sources)) in enumerate(zip(
                            plan['requirement_dispositions'], (
                                ('activation', 'measure_activation', ['native-cycle-frames.jsonl','native-map-readback.json','standing-vehicle.json','context.json']),
                                ('speed_exception', 'measure_speed_exception', ['native-cycle-frames.jsonl','context.json']),
                                ('left_turn_exception', 'measure_left_turn_exception', ['native-cycle-frames.jsonl','context.json']),
                                ('position_and_care', 'measure_position_and_care', ['native-cycle-frames.jsonl','native-map-readback.json','standing-vehicle.json']),
                                ('unsafe_context', 'measure_unsafe_context', ['native-cycle-frames.jsonl','standing-vehicle.json','context.json']),
                                ('object_hazard', 'measure_object_hazard', ['standing-vehicle.json','context.json']),
                                ('narrow_lane', 'measure_narrow_lane', ['native-map-readback.json','context.json']),
                                ('selected_witness', 'measure_selected_witness', ['native-cycle-frames.jsonl','standing-vehicle.json']))))]
        write(FOLDER / f'measurement-{label}.json', {'format': 'worker-measurement-contract',
            'requirements': requirements,
            'negative': {'remove': ['native-cycle-frames.jsonl'],
                         'error_contains': 'Missing required source: native-cycle-frames.jsonl'}})
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': AID, 'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'selected_cpu_construction_partial', 'cases': rows})
    print(json.dumps({'cases': IDS, 'manifest_sha256': sha(FOLDER / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
