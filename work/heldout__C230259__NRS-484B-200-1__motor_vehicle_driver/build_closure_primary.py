"""Construct the exact C230259 closure-left Native capture package."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__closure_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    construction = json.loads((HERE / 'construction-baseline_left.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'closure_runner.py'
    construction['mechanisms']['route'] = 'connected two-way left-half route beside three original right-half closure devices'
    construction['mechanisms']['control'] = 'bounded left-half route and speed feedback; closure authority undecided'
    construction['mechanisms']['construction_status'] = 'exact_closure_primary_offline_pending'
    construction['static_checks'] = [
        'Exact C230259 closure-left identity, 80 original ticks at 20 Hz',
        'Three distinct Native traffic-cone actors across the right-half lane interior',
        'Original closure device readback at each tick, original body/road geometry and four FFV1 cameras',
    ]
    construction['termination_rules'] = [
        'Stop after 80 original ticks',
        'Fail on missing actor, closure source frame, camera source or road-center geometry',
        'Close encoders and restore world settings',
    ]
    construction['recording_description']['limitations'].append(
        'Closure devices are original 20 Hz actor readback; traffic-control authority needs separate review.')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['case']['recording_description'] = construction['recording_description']
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['path'] = 'closure_runner.py'
            item['content'] = (HERE / 'closure_runner.py').read_text()
        elif item['path'].startswith('tests/'):
            item['path'] = 'tests/test_closure_runner_config.py'
            item['content'] = (HERE / item['path']).read_text()
    construction['files'] = list({item['path']: item for item in construction['files']}.values())
    construction['files'].append({'path': 'right_half_closure.py',
                                  'content': (HERE / 'right_half_closure.py').read_text()})
    construction['files'].append({'path': 'tests/test_right_half_closure.py',
                                  'content': (HERE / 'tests/test_right_half_closure.py').read_text()})
    construction['measurement_plan']['original_sources'].append('closure_devices.jsonl')
    path = HERE / 'construction-closure_left.json'
    write(path, construction)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [entry for entry in manifest['cases'] if entry['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery', 'construction': path.name,
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'right_half_finalizer.py'},
        'candidate_risk': {'status': 'physical', 'reason':
            'Native cone placement, left-half motion, four-camera visibility and closure authority need verification'},
        'candidates': [],
    })
    write(manifest_path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
