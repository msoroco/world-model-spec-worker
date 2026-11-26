"""Build exact selected Native device-zone constructions and source measurement contracts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = (('false', 'outside'), ('true', 'inside'))
CHANNELS = ('ego_pose', 'device_prohibited_place_occupancy', 'device_identity',
            'device_authority', 'device_instruction_and_scope', 'device_condition',
            'civil_time', 'vehicle_activity', 'traffic_conflict_context',
            'law_compliance_context', 'police_direction_context', 'device_direction_context',
            'source_camera_frame_join')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ['road.xodr', 'device-inventory.json', 'device-review.json',
           'condition-review.json', 'activity-review.json', 'exception-review.json',
           'vehicle-poses.jsonl', 'video_frames.jsonl', 'overview.mkv']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'selected_cpu_preparation', 'cases': []}
    method_keys = [('exception_observation','statutory_scope'),
        ('zone_observation','prohibited_place'),('zone_observation','narrow_road_park'),
        ('device_observation','device_identity_authority'),('device_observation','device_instruction_scope'),
        ('condition_observation','condition_and_time'),('activity_observation','vehicle_activity'),
        ('zone_observation','vehicle_footprint_rest'),('exception_observation','traffic_conflict_necessity'),
        ('exception_observation','compliance_with_law'),('exception_observation','police_direction'),
        ('exception_observation','device_direction'),
        ('activity_observation','stop_mode_alternative'),
        ('activity_observation','stand_mode_alternative')]
    assert len(method_keys) == len(plan['requirement_dispositions'])
    for suffix, zone_case in CASES:
        case = AID + '__' + suffix
        description = {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'original Native frame joined to independent device, condition, activity and exception source review',
            'time_window': '600 original frames', 'reference_frame': 'surveyed narrow road and Native frame',
            'uncertainty': '50 ms sampling; original authority and legal status require independent review',
            'source': 'channels/' + name + '.jsonl'} for name in CHANNELS],
            'context_inputs': [],
            'limitations': ['Authored sign and synthetic pixels do not establish official-device status, legal necessity or outcome.']}
        config = {'case_id': case, 'selected_case_id': case,
            'supported_case_ids': [AID + '__' + s for s, _ in CASES],
            'candidate_id': 'primary', 'law_id': 'NRS-484B-450-1o', 'cell_id': 'C135709',
            'actor': 'motor_vehicle_driver', 'zone_case': zone_case,
            'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
            'physical_completion': {'criterion': 'travel_progress', 'minimum_progress_m': 50,
                'completion_goal_method': 'Engineering approach progress from start to requested rest station; separate from stationary target and legal outcome.'},
            'case': {'case_id': case}, 'statutory_text': plan['source_law']['text'],
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720, 'fov_deg': 90,
                'pose_strategy': 'static surveyed device, approach and body coverage'} for name in CAMERAS],
            'recording_description': description, 'status': 'cpu_draft_original_authority_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py', 'measure_zone.py',
                              'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case, 'law_id': 'NRS-484B-450-1o', 'cell_id': 'C135709',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': SOURCES},
            'static_checks': ['200 m two-way narrow road', 'authored NO_PARKING device and surveyed zone',
                              '600 original frames at 20 Hz', 'four retained RGB cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
            'mechanisms': ['common feedback controller, varied requested station'],
            'status': 'selected_cpu_preparation_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case, 'requirements': [
            {'disposition_index': index, 'requirement': row['requirement'], 'source': row['source'],
             'output_key': key, 'method': method, 'value_type': 'object',
             'kind': 'measured' if index in (1,2,7) else 'sourced_context', 'inputs': SOURCES}
            for index, (row, (method,key)) in enumerate(zip(plan['requirement_dispositions'], method_keys))],
            'negative': {'remove': ['device-review.json'],
                         'error_contains': 'Missing required source: device-review.json'}}
        contract_path = HERE / 'draft-exact' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        fallback = json.loads(path.read_text())
        for item in fallback['files']:
            if item['path'] == 'runner.py':
                old = 'carla.Location(x=-80, y=-1.75, z=2.0)'
                if old not in item['content']:
                    raise ValueError('Fallback spawn knob missing')
                item['content'] = item['content'].replace(old, 'carla.Location(x=-78, y=-1.75, z=2.0)')
            if item['path'] == 'config.json':
                cfg = json.loads(item['content']); cfg['candidate_id'] = 'fallback1'
                item['content'] = json.dumps(cfg, indent=2) + '\n'
        fpath = HERE / 'draft-exact' / suffix / 'fallback1/construction.json'
        write(fpath, fallback)
        manifest['cases'].append({'case_id': case, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native stopping gain may place the vehicle short of the requested device-zone station; original rest and body footprint need inspection.'},
            'candidates': [{'id': 'fallback1', 'construction': str(fpath.relative_to(HERE)),
                'construction_sha256': sha(fpath),
                'trigger': {'source': 'original Native vehicle-poses.jsonl and result.json',
                    'metric': 'stationary footprint relative to requested device-zone station',
                    'failure_condition': 'five-second rest interval missing or measured zone occupancy disagrees with requested outside/inside target after source completeness checks'},
                'changed_knobs': ['initial vehicle spawn x -80 m to -78 m in both linked cases; controller and comparison variable fixed']}],
            'measurement_contract': str(contract_path.relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'selected_cpu_preparation'})
    write(HERE / 'draft-execution-manifest.json', manifest)
    print(json.dumps({row['case_id']: row['construction_sha256'] for row in manifest['cases']}))


if __name__ == '__main__':
    main()
