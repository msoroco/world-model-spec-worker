"""Bind the exact slow-left continuation pair to current-runtime constructions."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-208-1'
ACTOR = 'motor_vehicle_driver'
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
                                'rear_overtake_crossing', 'ego_lane_id',
                                'posted_speed_source', 'driver_notice_context',
                                'subsection_2_exception_context', 'camera_frame_join']))
    return {'channels': [{'name': name, 'unit': 'structured',
        'method': 'Original 600-frame ego/rear actor, lane readback and four-camera source join',
        'sampling_rate_hz': 20, 'time_window': '30 s / 600 original frames',
        'reference_frame': 'original Native map and frame',
        'uncertainty': 'Controlled-access posting, notice, exception and physical review pending'}
        for name in names],
        'context_inputs': [{'name': 'left_lane_statutory_context', 'unit': 'structured',
            'method': 'Source-hashed map, speed posting, knowledge and exception inventory'}],
        'limitations': ['Authored speed target is not an original posted-limit source.',
                        'Scripted actor trajectories test acquisition and measurement, not ordinary driving behavior or legal compliance.']}


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    desc = recording()
    proposals = []
    for case_id, continued in zip(IDS, (True, False)):
        proposals.append({'case_id': case_id, 'target_law_id': LAW,
            'target_type': 'controlled_comparison',
            'rationale': 'Measure slower left-lane continuation during a faster rear overtake; preserve activation, notice and subsection 2 review.',
            'variable_assignments': {
                'slow_extreme_left_lane_continuation': {'kind': 'controller',
                    'unit': 'boolean', 'value': continued},
                'road_and_rear_overtake': {'kind': 'world_setup', 'unit': 'categorical',
                    'value': 'same two-lane road, ego speed, faster rear actor, clear weather and four cameras'}},
            'paired_probe_id': AID + '__left_lane_pair',
            'deliberate_differences': ['slow_extreme_left_lane_continuation'],
            'probe': {'primary_variable': 'slow_extreme_left_lane_continuation',
                'comparison_or_standard': 'measured post-overtake left occupancy, not legal verdict',
                'target_value_or_branch': continued},
            'unresolved_judgment_calls': ['controlled-access highway classification',
                'driver knows or reasonably should know posted speed',
                'subsection 2 exceptions'],
            'recording_description': desc})
    write(FOLDER / 'proposals/cases.json', {'format': 'worker-case-proposals',
        'cell_id': 'C230259', 'actor': ACTOR, 'law_id': LAW, 'status': 'draft',
        'cases': proposals, 'sweep_specs': [], 'sweeps_expanded': True})
    native_files = ('runner.py', 'capture.py', 'geometry.py', 'left_lane_measure.py',
                    'saved_left_lane_finalizer.py', 'finalize.py', 'tests/test_capture.py')
    rows = []
    measurement_mapping = {
        'text-0': ('activation', 'measure_activation',
                   ['native-map-readback.json', 'native-road-context.json']),
        'text-1': ('speed_and_overtake', 'measure_speed_and_overtake',
                   ['native-actors.jsonl', 'native-road-context.json']),
        'text-6': ('maintenance_exception', 'measure_maintenance_exception',
                   ['context.json']),
        'reviewed-scope-0': ('selected_witness', 'measure_selected_witness',
                   ['native-actors.jsonl', 'native-road-context.json'])}
    for case_id, continued in zip(IDS, (True, False)):
        label = case_id.rsplit('__', 1)[-1]
        entry = {'case_id': case_id, 'kind': 'delivery', 'id': 'primary',
            'candidate_risk': {'status': 'physical',
                'reason': 'Rear actor may fail to spawn at the authored road origin or miss the intended overtake window.'},
            'candidates': [], 'measurement_contract': f'measurement-{label}.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                'output_schema': 'c230259-left-lane-saved-analysis-v1'},
            'fixture_recipe': f'work/{AID}/diagnostic-{label}-primary-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {item['name']: {'entrypoint': 'finalize.py',
                'method': 'original actor/overtake/lane and context source join',
                'evidence': 'Synthetic diagnostic only; original physical review pending'}
                for item in desc['channels']}}
        for candidate, rear_x in (('primary', -50), ('fallback1', -55)):
            config = {'case_id': case_id, 'selected_case_id': case_id,
                'supported_case_ids': IDS, 'candidate_id': candidate,
                'law_id': LAW, 'cell_id': 'C230259', 'actor': ACTOR,
                'condition': label, 'rate_hz': 20, 'duration_s': 30,
                'required_atoms': [], 'source_packets': [],
                'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                             'height': 1080 if name == 'overview' else 720,
                             'pose_strategy': 'fixed lane-and-overtake corridor',
                             'fov_deg': 85} for name in VIEWS],
                'slow_extreme_left_lane_continuation': continued,
                'rear_initial_x_m': rear_x, 'case': proposals[IDS.index(case_id)],
                'recording_description': desc,
                'physical_completion': {'criterion': 'travel_progress',
                    'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                    'minimum_progress_m': 100,
                    'engineering_tolerances_not_legal': True}}
            files = [{'path': name, 'source': f'work/{AID}/native/{name}',
                      'content': (FOLDER / 'native' / name).read_text()}
                     for name in native_files]
            files.append({'path': 'config.json',
                          'content': json.dumps(config, indent=2) + '\n'})
            construction = {'case_id': case_id, 'cell_id': 'C230259',
                'law_id': LAW, 'actor': ACTOR, 'entrypoint': 'runner.py',
                'files': files, 'recording_description': desc,
                'status': 'selected_cpu_construction',
                'measurement_plan': 'Saved original actor/lane/overtake sources and four cameras; posting, notice and exceptions remain independent review.',
                'static_checks': ['two marked Native lanes',
                                  '600 original frame actor and four camera join'],
                'termination_rules': ['600 original frames at 20 Hz',
                                      'reject source gaps and restore owned world'],
                'mechanisms': ['scripted Native ego and rear actors',
                               'road and lane readback',
                               'source-joined saved measurement and review']}
            path = FOLDER / 'native/selected-drafts' / label / candidate / 'construction.json'
            write(path, construction)
            binding = {'construction': str(path.relative_to(FOLDER)),
                       'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(binding)
            else:
                entry['candidates'].append({'id': 'fallback1', **binding,
                    'trigger': {'source': 'native-capture-report.json',
                        'metric': 'rear_spawn_and_overtake_window',
                        'failure_condition': 'rear spawn failed or overtake crossing absent'},
                    'changed_knobs': ['rear_initial_x_m -5 m']})
        rows.append(entry)
        requirements = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if (disposition['status'] == 'selected_required' and
                    case_id in disposition.get('case_ids', IDS)):
                key, method, sources = measurement_mapping[disposition['requirement']]
                requirements.append({'disposition_index': index,
                    'requirement': disposition['requirement'],
                    'source': disposition['source'], 'output_key': key,
                    'method': method, 'value_type': 'object', 'kind': 'measured',
                    'inputs': sources})
        write(FOLDER / f'measurement-{label}.json', {
            'format': 'worker-measurement-contract', 'requirements': requirements,
            'negative': {'remove': ['native-actors.jsonl'],
                'error_contains': 'Missing required source: native-actors.jsonl'}})
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': AID,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'selected_cpu_construction_partial', 'cases': rows})
    print(json.dumps({'cases': IDS,
                      'manifest_sha256': sha(FOLDER / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
