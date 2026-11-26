"""Build exact current-runtime entry candidates and selected measurement contracts."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CAMERAS = ('overview', 'approach', 'indicated_gate', 'highway_side')
CHANNELS = ('st.controlled_access', 'dev.regulatory_sign', 'dev.governs',
            'rel.occupies', 'kin.path_length', 'st.lane_connectivity', 'kin.position')
SOURCES = ['road.xodr', 'access-inventory.json', 'access-review.json',
           'device-review.json', 'actor-poses.jsonl', 'video_frames.jsonl',
           'overview.mkv', 'access-authority.txt', 'device-authority.txt',
           'device-content.txt', 'device-erection.txt', 'entrance-extent.txt',
           'highway-dedication.txt', 'public-use.txt', 'jurisdiction.txt',
           'vehicle-eligibility.txt']


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
    ids = [AID + '__witness_1', AID + '__witness_2']
    for suffix in ('witness_1', 'witness_2'):
        case = AID + '__' + suffix
        description = {'channels': [{'name': name, 'unit': 'structured',
            'sampling_rate_hz': 20,
            'method': 'Original Native body/frame join with distinct access and device source reviews',
            'time_window': '600 original frames',
            'reference_frame': 'surveyed highway edge and indicated entrance extent',
            'uncertainty': '50 ms sampling; physical and official authority review pending',
            'source': 'channels/' + name + '.jsonl'} for name in CHANNELS],
            'context_inputs': [],
            'limitations': ['Synthetic source context does not establish controlled-access designation, official device authority, physical success, or legal outcome.']}
        config = {'case_id': case, 'selected_case_id': case,
            'supported_case_ids': ids, 'candidate_id': 'primary',
            'law_id': 'NRS-484B-587-1', 'cell_id': 'C228131',
            'actor': 'motor_vehicle_driver', 'entry_mode': suffix,
            'steer_gain': .10, 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [],
            'physical_completion': {'criterion': 'travel_progress',
                'minimum_progress_m': 20,
                'completion_goal_method': 'Engineering route progress from original sampled positions; no statutory threshold.'},
            'case': {'case_id': case}, 'statutory_text': plan['source_law']['text'],
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720, 'fov_deg': 90,
                'pose_strategy': 'static survey of entrance, approach and highway edge'} for name in CAMERAS],
            'recording_description': description,
            'status': 'cpu_prepared_original_authority_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'route.py', 'finalize.py',
                              'tests/test_native.py')]
        files.append({'path': 'saved_entry.py', 'content': (HERE / 'saved_entry.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case, 'law_id': 'NRS-484B-587-1',
            'cell_id': 'C228131', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': SOURCES},
            'static_checks': ['authored highway/frontage/entrance paving',
                              '600 original frames at 20 Hz', 'four source cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
            'mechanisms': ['same map, device candidate and controller; requested crossing x varies'],
            'status': 'selected_cpu_preparation_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{'disposition_index': index,
                'requirement': plan['requirement_dispositions'][index]['requirement'],
                'source': plan['requirement_dispositions'][index]['source'],
                'output_key': key, 'method': method, 'value_type': 'object',
                'kind': kind, 'inputs': SOURCES}
                for index, key, method, kind in (
                    (0, 'entry_position', 'entry_position', 'measured'),
                    (1, 'controlled_access_context', 'controlled_access_context', 'sourced_context'),
                    (2, 'official_device_context', 'official_device_context', 'sourced_context'),
                    (3, 'vehicle_context', 'vehicle_context', 'sourced_context'))],
            'negative': {'remove': ['device-authority.txt'],
                         'error_contains': 'Missing required source: device-authority.txt'}}
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
            'candidate_risk': {'status': 'physical',
                'reason': 'Original motor-vehicle steering can oscillate while crossing frontage, ramp and highway pavement, missing the requested edge-crossing point.'},
            'candidates': [{'id': 'fallback1',
                'construction': str(fallback_path.relative_to(HERE)),
                'construction_sha256': sha(fallback_path),
                'trigger': {'source': 'original actor-poses.jsonl, trace.jsonl and result.json',
                    'metric': 'lateral tracking and measured highway-edge crossing x',
                    'failure_condition': 'oscillation, off-pavement body motion, or measured crossing misses the selected target after source completeness review'},
                'changed_knobs': ['common steering gain 0.10 to 0.07 across the pair; same map, sign, route target, cameras, duration and comparison variable']}],
            'measurement_contract': str(contract_path.relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'selected_cpu_preparation'})
    write(HERE / 'draft-execution-manifest.json', manifest)
    print({row['case_id']: row['construction_sha256'] for row in manifest['cases']})


if __name__ == '__main__':
    main()
