"""Build the selected ego-right comparison as a separate CPU construction.

The site is a synthetic schema exercise; this does not assert a real crossing.
"""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEFT = HERE.name + '__off_ego_left_near_time'
RIGHT = HERE.name + '__off_ego_right_near_time'
OUT = HERE/'cases/off_ego_right_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    primary = json.loads((HERE/'construction.json').read_text())
    files = {item['path']: item['content'] for item in primary['files']}
    config = json.loads(files['config.json'])
    config['selected_case_id'] = RIGHT
    config['other_approach_side'] = 'left'
    site = config['site']
    site['ego_highway_id'], site['other_highway_id'] = site['other_highway_id'], site['ego_highway_id']
    site['ego_approach'], site['other_approach'] = site['other_approach'], site['ego_approach']
    site['ego_entry'], site['other_entry'] = site['other_entry'], site['ego_entry']
    site['routes']['ego'], site['routes']['other'] = site['routes']['other'], site['routes']['ego']
    spec = importlib.util.spec_from_file_location('test_runner', HERE/'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as temporary:
        site_dir = Path(temporary)
        module.write_review(site_dir, config)
        packet = {path.name: path.read_text() for path in site_dir.iterdir() if path.is_file()}
    files['config.json'] = json.dumps(config, indent=2, allow_nan=False)+'\n'
    files.update(packet)
    runner = files['runner.py'].replace(LEFT, RIGHT)
    runner = runner.replace("config.get('other_approach_side') != 'right'", "config.get('other_approach_side') != 'left'")
    runner = runner.replace("carla.TrafficLightState, 'right')", "carla.TrafficLightState, 'left')")
    runner = runner.replace('Other approach must be on ego right for ego-left case',
                            'Other approach must be on ego left for ego-right case')
    if runner == files['runner.py'] or "carla.TrafficLightState, 'left')" not in runner:
        raise ValueError('Right-case Native runner variant was not constructed')
    files['runner.py'] = runner
    files['finalizer.py'] = files['finalizer.py'].replace(LEFT, RIGHT)
    construction = copy.deepcopy(primary)
    construction['case_id'] = RIGHT
    construction['status'] = 'synthetic_diagnostic_only'
    for item in construction['files']:
        if item['path'] in files:
            item['content'] = files[item['path']]
            item.pop('source', None)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'construction.json'
    path.write_text(json.dumps(construction, indent=2, allow_nan=False)+'\n')
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if any(row['case_id'] == RIGHT for row in manifest['cases']):
        raise ValueError('Right case already exists; retain bound proofs')
    manifest['cases'].append({
        'case_id': RIGHT, 'kind': 'delivery',
        'construction': str(path.relative_to(HERE)),
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'finalizer.py'},
        'measurement_contract': 'measurement-contract.json',
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'candidate_risk': {'status': 'physical',
                           'reason': 'Reversed approach orientation may fail the Native entry route or original camera coverage.'},
    })
    manifest['status'] = 'partial_two_case_construction'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': RIGHT, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
