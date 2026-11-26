"""Bind exact selected Native constructions, measurement contracts and fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'away'), ('probe_2', 'beside'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'selected_cpu_preparation'
    for suffix, parking_case in CASES:
        case = ASSIGNMENT + '__' + suffix
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        path = HERE / entry['construction']
        construction = json.loads(path.read_text())
        files = {row['path']: row for row in construction['files']}
        for name in ('runner.py', 'geometry.py', 'controller.py', 'measure_parking.py',
                     'finalize.py', 'tests/test_native.py'):
            files[name] = {'path': name, 'content': (HERE / 'native' / name).read_text()}
        config = json.loads(files['config.json']['content'])
        for row, name in zip(config['cameras'], ('overview', 'approach', 'reference_corner', 'driver_reference')):
            row['name'] = name
        for row in config['cameras']:
            row['width'], row['height'] = (1920, 1080) if row['name'] == 'overview' else (1280, 720)
            row['pose_strategy'] = 'static surveyed frontage and parking body view'
            row['fov_deg'] = 90
        description = construction['recording_description']
        description['context_inputs'] = []
        terms = [term['term'] for term in plan['mandatory_observation_terms']]
        present = {channel['name'] for channel in description['channels']}
        for name in terms:
            if name not in present:
                description['channels'].append({'name': name, 'unit': 'structured',
                    'sampling_rate_hz': 20, 'method': 'original frame joined with independent park, vehicle or exception source review',
                    'time_window': '600 original frames', 'reference_frame': 'surveyed narrow road and original Native frame',
                    'uncertainty': '50 ms sampling; external classification requires independent review'})
        for channel in description['channels']:
            channel['source'] = 'channels/' + channel['name'] + '.jsonl'
        config['recording_description'] = description
        config['candidate_id'] = 'primary'
        config['statutory_text'] = plan['source_law']['text']
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        construction['files'] = list(files.values())
        construction['measurement_plan'] = {'entrypoint': 'finalize.py',
            'required_sources': ['road.xodr', 'frontage-inventory.json',
                'park-review.json', 'vehicle-spec-review.json', 'exception-review.json',
                'vehicle-poses.jsonl', 'video_frames.jsonl', 'overview.mkv']}
        write(path, construction)
        entry['construction_sha256'] = sha(path)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [], 'negative': {'remove': ['park-review.json'],
            'error_contains': 'Missing required source: park-review.json'}}
        methods = ('measured', 'sign_observation', 'alternative_place_observation',
                   'alternative_place_observation', 'loading_observation',
                   'service_observation', 'vehicle_observation',
                   'park_context_observation', 'commercial_basis_observation',
                   'parking_purpose_observation', 'device_observation',
                   'interpretive_reservations_observation')
        keys = ('parking_adjacency', 'posted_sign_permission',
                'residence_district_definition', 'public_school',
                'loading_delivery_exception', 'essential_local_service_exception',
                'size_weight_scope', 'public_park_access_jurisdiction',
                'commercial_enterprise_basis', 'parking_purpose_storage',
                'device_authority_area', 'modifier_scope_exceptions')
        inputs = ['road.xodr', 'frontage-inventory.json', 'park-review.json',
                  'vehicle-spec-review.json', 'exception-review.json',
                  'vehicle-poses.jsonl', 'video_frames.jsonl', 'overview.mkv']
        for i, row in enumerate(plan['requirement_dispositions']):
            contract['requirements'].append({'disposition_index': i,
                'requirement': row['requirement'], 'source': row['source'],
                'output_key': keys[i], 'method': methods[i], 'value_type': 'object',
                'kind': 'measured' if i in (0, 6) else 'sourced_context', 'inputs': inputs})
        contract_path = HERE / 'draft-exact' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        entry['measurement_contract'] = str(contract_path.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'finalize.py'}
        entry['fixture_recipe'] = 'work/' + ASSIGNMENT + '/diagnostic-' + suffix + '-recipe.json'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        # The initial station can miss the requested frontage before a fixed 30 s stop.
        fallback = json.loads(path.read_text())
        for row in fallback['files']:
            if row['path'] == 'runner.py':
                old = 'carla.Location(x=-80, y=-1.75, z=2.0)'
                new = 'carla.Location(x=-78, y=-1.75, z=2.0)'
                if old not in row['content']:
                    raise ValueError('Fallback spawn knob missing')
                row['content'] = row['content'].replace(old, new)
            elif row['path'] == 'config.json':
                cfg = json.loads(row['content']); cfg['candidate_id'] = 'fallback1'
                row['content'] = json.dumps(cfg, indent=2) + '\n'
        fpath = HERE / 'draft-exact' / suffix / 'fallback1' / 'construction.json'
        write(fpath, fallback)
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Controller stopping gain may place the heavy vehicle short of the requested park frontage; original rest interval and footprint need inspection'}
        entry['candidates'] = [{'id': 'fallback1', 'construction': str(fpath.relative_to(HERE)),
            'construction_sha256': sha(fpath),
            'trigger': {'source': 'original Native vehicle-poses.jsonl and result.json',
                        'metric': 'stationary footprint at requested frontage station',
                        'failure_condition': 'five-second rest interval missing or parked footprint disagrees with requested away/beside target after source completeness checks'},
            'changed_knobs': ['initial vehicle spawn x from -80 m to -78 m in both linked cases; controller and all observation contracts fixed']}]
    write(HERE / 'draft-execution-manifest.json', manifest)
    print(json.dumps({e['case_id']: e['construction_sha256'] for e in manifest['cases']}))


if __name__ == '__main__':
    main()
