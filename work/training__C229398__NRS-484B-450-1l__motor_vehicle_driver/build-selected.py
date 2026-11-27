"""Build selected two-vehicle curbside Native bundles and measurement contracts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-450-1l'
CASES = ('clear', 'stop', 'stand', 'park', 'traffic_conflict',
         'law_direction', 'police_direction', 'device_direction')
CHANNELS = ('ego_pose', 'curbside_pose', 'curb_geometry',
            'ego_highway_side_of_curbside', 'longitudinal_overlap_m',
            'lateral_surface_gap_m', 'concurrent_overlap_at_rest',
            'longest_concurrent_run_frames', 'activity_context',
            'traffic_conflict_context', 'law_compliance_context',
            'police_direction_context', 'device_direction_context',
            'source_camera_frame_join')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'map-geometry.json', 'vehicle-poses.jsonl',
           'body-footprints.jsonl', 'video_frames.jsonl', 'highway-review.json',
           'activity-review.json', 'exception-review.json', 'pixel-review.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
OUTPUT_KEYS = ('highway_side_place', 'stop_mode', 'stand_mode', 'park_mode',
               'traffic_conflict_necessity', 'compliance_with_law',
               'police_direction', 'device_direction')
METHODS = ('place_observation', 'activity_observation', 'activity_observation',
           'activity_observation', 'exception_observation', 'exception_observation',
           'exception_observation', 'exception_observation')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'selected_cpu_preparation', 'cases': []}
    case_ids = [AID + '__' + suffix for suffix in CASES]
    description = {'channels': [{'name': name, 'unit': 'structured',
        'sampling_rate_hz': 20,
        'method': 'original two-actor footprint and Native frame joined to independent curb, activity, exception and pixel source',
        'time_window': '600 original frames',
        'reference_frame': 'surveyed highway curb and Native frame',
        'uncertainty': '50 ms sampling; legal activity and exception require independent review',
        'source': 'channels/' + name + '.jsonl'} for name in CHANNELS],
        'context_inputs': [],
        'limitations': ['Synthetic two-vehicle geometry does not establish original highway designation, activity, exception or legal outcome.']}
    for suffix in CASES:
        case = AID + '__' + suffix
        activity = 'neutral' if suffix == 'clear' else suffix if suffix in ('stop', 'stand', 'park') else 'park'
        config = {'case_id': case, 'selected_case_id': case,
            'supported_case_ids': case_ids, 'candidate_id': 'primary',
            'law_id': LAW, 'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
            'activity_request': activity, 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [],
            'physical_completion': {'criterion': 'travel_progress',
                'minimum_progress_m': 50,
                'completion_goal_method': 'Engineering approach progress from spawn to requested rest station; legal classification separate.'},
            'case': {'case_id': case}, 'statutory_text': plan['source_law']['text'],
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720, 'fov_deg': 90,
                'pose_strategy': 'static surveyed curb, both vehicle bodies and approach'} for name in CAMERAS],
            'recording_description': description,
            'status': 'cpu_draft_original_highway_activity_exception_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py',
                              'double_parking_meter.py', 'finalize.py',
                              'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'})
        construction = {'case_id': case, 'law_id': LAW, 'cell_id': 'C229398',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': list(SOURCES)},
            'static_checks': ['two-direction road with travel and curbside parking lanes',
                              'two original vehicle actors with surveyed curb',
                              '600 original frames at 20 Hz', 'four retained RGB cameras'],
            'termination_rules': ['600 joined frames', 'destroy owned actors and restore world'],
            'mechanisms': ['common feedback policy, varied requested rest station and separately sourced exception'],
            'status': 'selected_cpu_preparation_original_physical_unverified'}
        path = HERE / 'selected-cases' / suffix / 'primary/construction.json'
        write(path, construction)
        selected = {i for i, row in enumerate(plan['requirement_dispositions'])
                    if case in row['case_ids']}
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{'disposition_index': i,
                'requirement': plan['requirement_dispositions'][i]['requirement'],
                'source': plan['requirement_dispositions'][i]['source'],
                'output_key': OUTPUT_KEYS[i], 'method': METHODS[i],
                'value_type': 'object',
                'kind': 'measured' if i <= 3 else 'sourced_context',
                'inputs': list(SOURCES)} for i in sorted(selected)],
            'negative': {'remove': ['highway-review.json'],
                         'error_contains': 'Missing required source: highway-review.json'}}
        contract_path = HERE / 'selected-cases' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        fallback = json.loads(path.read_text())
        for item in fallback['files']:
            if item['path'] == 'runner.py':
                old = 'carla.Location(x=-80, y=EGO_LATERAL, z=2.0)'
                if old not in item['content']:
                    raise ValueError('Fallback spawn knob missing')
                item['content'] = item['content'].replace(old, 'carla.Location(x=-78, y=EGO_LATERAL, z=2.0)')
            if item['path'] == 'config.json':
                changed = json.loads(item['content']);changed['candidate_id'] = 'fallback1'
                item['content'] = json.dumps(changed, indent=2, ensure_ascii=False) + '\n'
        fallback_path = HERE / 'selected-cases' / suffix / 'fallback1/construction.json'
        write(fallback_path, fallback)
        manifest['cases'].append({'case_id': case, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Original stop controller may miss the requested longitudinal rest station while the curbside body and camera geometry remain fixed.'},
            'candidates': [{'id': 'fallback1', 'construction': str(fallback_path.relative_to(HERE)),
                'construction_sha256': sha(fallback_path),
                'trigger': {'source': 'original Native vehicle-poses.jsonl and body-footprints.jsonl',
                    'metric': 'subject rest station and longitudinal overlap from 600 source frames',
                    'failure_condition': 'stationary interval missing or original body overlap differs from requested case after source completeness checks'},
                'changed_knobs': ['subject initial spawn x -80 m to -78 m in every linked case; curbside actor and comparison policy fixed']}],
            'measurement_contract': str(contract_path.relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'selected_cpu_preparation'})
    write(HERE / 'draft-execution-manifest.json', manifest)
    print(json.dumps({'cases': len(manifest['cases']),
                      'primary_sha256': {row['case_id']: row['construction_sha256']
                                         for row in manifest['cases']}}))


if __name__ == '__main__':
    main()
