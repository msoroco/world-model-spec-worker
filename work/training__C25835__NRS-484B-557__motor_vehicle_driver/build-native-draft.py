"""Build exact source-hashed five-case Native rail-stop draft and fallback."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('dev.stop_sign', 'dev.governs', 'st.railway_crossing',
            'rel.centre_distance', 'drv.stopped', 'drv.approaching',
            'drv.time_to_conflict', 'ru.rail_vehicle')
SOURCES = ['road.xodr', 'rail-inventory.json', 'rail-trace.jsonl',
           'video_frames.jsonl', 'designation-authority.txt', 'sign-authority.txt',
           'designation-review.json', 'sign-review.json', 'occluder-review.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv']
TARGETS = {'probe_1': 25.0, 'probe_2': 10.0, 'probe_3': 15.0,
           'probe_4': 50.0, 'probe_5': 50.5}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [AID + '__' + suffix for suffix in TARGETS]
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256'],
        'status': 'partial_selected_preparation', 'cases': []}
    description = {'channels': [{'name': name, 'unit': 'structured',
        'sampling_rate_hz': 20,
        'method': 'Original Native rail/vehicle/frame join with independent designation and official-sign reviews',
        'time_window': '600 original frames',
        'reference_frame': 'nearest track approach edge; front, centre and rear retained',
        'uncertainty': '50 ms sampling; vehicle reference point and due care require independent review',
        'source': 'channels/' + name + '.jsonl'} for name in CHANNELS],
        'context_inputs': [],
        'limitations': ['Authored props and synthetic fixtures cannot establish administrative designation, official sign authority, actual pixels, physical completion, due care, or legal outcome.']}
    for suffix, target in TARGETS.items():
        case = AID + '__' + suffix
        config = {'case_id': case, 'selected_case_id': case,
            'supported_case_ids': ids, 'candidate_id': 'primary',
            'law_id': 'NRS-484B-557', 'cell_id': 'C25835',
            'actor': 'motor_vehicle_driver', 'requested_stop_center_ft': target,
            'brake_gain': .7, 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [],
            'physical_completion': {'criterion': 'travel_progress',
                'minimum_progress_m': 20,
                'completion_goal_method': 'Original vehicle progress across requested crossing; engineering event criterion, not statutory stop or due-care rule.'},
            'case': {'case_id': case}, 'statutory_text': plan['source_law']['text'],
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720, 'fov_deg': 90,
                'pose_strategy': 'static survey of approach, stop sign, nearest rail and crossing'}
                for name in CAMERAS],
            'recording_description': description,
            'status': 'cpu_prepared_original_authority_unverified'}
        files = [{'path': name, 'content': (HERE / ('native/' + name) if name in
                  ('runner.py', 'finalize.py', 'tests/test_native.py') else HERE / name).read_text()}
                 for name in ('runner.py', 'finalize.py', 'rail_stop_controller.py',
                              'rail_stop_scene.py', 'rail_stop_measure.py',
                              'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case, 'law_id': 'NRS-484B-557',
            'cell_id': 'C25835', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': SOURCES},
            'static_checks': ['authored two-way approach with rail, sign and occluder props',
                              'five exact requested stop stations',
                              '600 original frames at 20 Hz and four source cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and restore Native world'],
            'mechanisms': ['same map, vehicle, rails, sign, occluder and controller; requested centre stop station varies'],
            'status': 'selected_cpu_preparation_physical_unverified'}
        path = HERE / 'draft-native' / suffix / 'primary/construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{'disposition_index': index,
                'requirement': plan['requirement_dispositions'][index]['requirement'],
                'source': plan['requirement_dispositions'][index]['source'],
                'output_key': key, 'method': method, 'value_type': 'object',
                'kind': kind, 'inputs': SOURCES}
                for index, key, method, kind in (
                    (0, 'approach_proceeding', 'approach_proceeding', 'measured'),
                    (1, 'stop_position', 'stop_position', 'measured'),
                    (2, 'crossing_designation', 'crossing_designation', 'sourced_context'),
                    (3, 'official_stop_sign', 'official_stop_sign', 'sourced_context'),
                    (4, 'due_care_context', 'due_care_context', 'sourced_context'))],
            'negative': {'remove': ['designation-authority.txt'],
                         'error_contains': 'Missing required source: designation-authority.txt'}}
        contract_path = HERE / 'draft-native' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        fallback = copy.deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'config.json':
                fallback_config = json.loads(item['content'])
                fallback_config['candidate_id'] = 'fallback1'
                fallback_config['brake_gain'] = .9
                item['content'] = json.dumps(fallback_config, indent=2) + '\n'
        fallback_path = HERE / 'draft-native' / suffix / 'fallback1/construction.json'
        write(fallback_path, fallback)
        manifest['cases'].append({'case_id': case, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Original vehicle inertia may overshoot the requested stop station, especially at the 15-ft inner boundary.'},
            'candidates': [{'id': 'fallback1',
                'construction': str(fallback_path.relative_to(HERE)),
                'construction_sha256': sha(fallback_path),
                'trigger': {'source': 'original rail-trace.jsonl and result.json',
                    'metric': 'observed first cessation centre distance from source-identified nearest rail',
                    'failure_condition': 'vehicle overshoots requested station or does not reach complete cessation on the original 600-frame trace'},
                'changed_knobs': ['same controller across all linked cases; braking gain 0.7 to 0.9 only']}],
            'measurement_contract': str(contract_path.relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'selected_cpu_preparation'})
    write(HERE / 'draft-native-manifest.json', manifest)
    print({row['case_id']: row['construction_sha256'] for row in manifest['cases']})


if __name__ == '__main__':
    main()
