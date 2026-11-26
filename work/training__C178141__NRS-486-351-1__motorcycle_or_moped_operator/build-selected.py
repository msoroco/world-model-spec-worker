"""Build the source-bound current-runtime stationary motorcycle pair."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = (('probe_1', 'beside', 'stationary', 'motorcycle', False),
         ('probe_2', 'between', 'stationary', 'motorcycle', False),
         ('probe_3', 'between', 'moving', 'motorcycle', False),
         ('probe_4', 'between', 'stationary', 'moped', False),
         ('probe_5', 'between', 'stationary', 'motorcycle', True))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('ru.subject', 'ru.motorcycle', 'ru.moped', 'st.lane_adjacency',
            'rel.occupies', 'drv.straddles_marking', 'rel.bearing',
            'rel.longitudinal_overlap', 'ru.motor_vehicle', 'kin.velocity')
SOURCES = ['road.xodr', 'lane-inventory.json', 'split-review.json',
           'classification-review.json', 'duty-review.json',
           'actor-poses.jsonl', 'video_frames.jsonl', 'overview.mkv']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256'],
                'status': 'partial_selected_preparation', 'cases': []}
    ids = [AID + '__' + row[0] for row in CASES]
    for suffix, split_case, surrounding_mode, machine_candidate, police_duty_requested in CASES:
        case = AID + '__' + suffix
        description = {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'original Native body/road/frame join and separately reviewed classification and duty context',
            'time_window': '600 original frames', 'reference_frame': 'surveyed adjacent lanes and Native frame',
            'uncertainty': '50 ms sampling; original physical/legal status requires independent review',
            'source': 'channels/' + name + '.jsonl'} for name in CHANNELS],
            'context_inputs': [], 'limitations': ['Synthetic pixels and authored roles do not establish motorcycle or moped legal classification, police duty, or legal outcome.']}
        config = {'case_id': case, 'selected_case_id': case, 'supported_case_ids': ids,
            'candidate_id': 'primary', 'law_id': 'NRS-486-351-1', 'cell_id': 'C178141',
            'actor': 'motorcycle_or_moped_operator', 'split_case': split_case,
            'surrounding_mode': surrounding_mode, 'machine_candidate': machine_candidate,
            'police_duty_requested': police_duty_requested, 'steer_gain': .1,
            'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
            'physical_completion': {'criterion': 'travel_progress', 'minimum_progress_m': 40,
                'completion_goal_method': 'Engineering route progress from original sampled motorcycle positions; no legal threshold.'},
            'case': {'case_id': case}, 'statutory_text': plan['source_law']['text'],
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720, 'fov_deg': 90,
                'pose_strategy': 'static surveyed adjacent lanes and all body histories'} for name in CAMERAS],
            'recording_description': description, 'status': 'cpu_draft_original_classification_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'route.py', 'measure_split.py',
                              'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case, 'law_id': 'NRS-486-351-1', 'cell_id': 'C178141',
            'actor': 'motorcycle_or_moped_operator', 'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': SOURCES},
            'static_checks': ['160 m paved adjacent lanes', 'Native lane/actor survey',
                              '600 original frames at 20 Hz', 'four retained RGB cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
            'mechanisms': ['same two lane occupants and speed request; subject lateral path varies'],
            'status': 'selected_cpu_preparation_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{'disposition_index': index, 'requirement': row['requirement'],
                'source': row['source'], 'output_key': key, 'method': method,
                'value_type': 'object', 'kind': kind, 'inputs': SOURCES}
                for index, row in enumerate(plan['requirement_dispositions'])
                if case in row['case_ids']
                for key, method, kind in [(
                    ('stationary_between', 'position_observation', 'measured'),
                    ('moving_or_stationary', 'lane_observation', 'measured'),
                    ('police_duty_exception', 'duty_observation', 'sourced_context'),
                    ('machine_classification', 'classification_observation', 'sourced_context'))[index]]],
            'negative': {'remove': ['split-review.json'],
                         'error_contains': 'Missing required source: split-review.json'}}
        contract_path = HERE / 'draft-exact' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        fallback = copy.deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'config.json':
                fallback_config = json.loads(item['content'])
                fallback_config['candidate_id'] = 'fallback1'
                fallback_config['steer_gain'] = .07
                item['content'] = json.dumps(fallback_config, indent=2) + '\n'
        fallback_path = HERE / 'draft-exact' / suffix / 'fallback1/construction.json'
        write(fallback_path, fallback)
        manifest['cases'].append({'case_id': case, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical', 'reason': 'Original lateral tracking may oscillate near occupied adjacent-lane bodies, reducing physical clearance or losing the between/ beside target.'},
            'candidates': [{'id': 'fallback1', 'construction': str(fallback_path.relative_to(HERE)),
                'construction_sha256': sha(fallback_path),
                'trigger': {'source': 'original actor-poses.jsonl, trace.jsonl and result.json',
                    'metric': 'sampled lateral error, body clearance and selected between-vehicle target',
                    'failure_condition': 'original body contact/insufficient clearance, unstable lateral oscillation, or target mismatch after source completeness review'},
                'changed_knobs': ['common subject steering feedback gain 0.10 to 0.07 in every linked case; route, participants, cameras, duration and comparison variable fixed']}], 'measurement_contract': str(contract_path.relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'selected_cpu_preparation'})
    write(HERE / 'draft-execution-manifest.json', manifest)
    print(json.dumps({row['case_id']: row['construction_sha256'] for row in manifest['cases']}))


if __name__ == '__main__':
    main()
