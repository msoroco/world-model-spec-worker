"""Construct the exact C230259 three-lane left-half Native capture package."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__three_lane_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    construction = json.loads((HERE / 'construction-baseline_left.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'three_lane_runner.py'
    construction['mechanisms']['route'] = ('connected three-driving-lane Native route '
                                           'with two outbound lanes and one opposing outer lane')
    construction['mechanisms']['control'] = ('bounded left-half outer-lane feedback; '
                                             'applicable lane-rule judgment undecided')
    construction['mechanisms']['construction_status'] = 'exact_three_lane_primary_offline_pending'
    construction['static_checks'] = [
        'Exact C230259 three-lane-left identity, 80 original ticks at 20 Hz',
        'Three distinct joined Native driving lanes, two outbound and one opposing',
        'Original lane inventory, full body/road geometry and four FFV1 source cameras',
    ]
    construction['termination_rules'] = [
        'Stop after 80 original ticks',
        'Fail on missing lane, changed direction, source frame or camera',
        'Close encoders and restore world settings',
    ]
    construction['recording_description']['limitations'].append(
        'Three-lane inventory is original Native map readback; applicable lane-law status needs separate review.')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['case']['recording_description'] = construction['recording_description']
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['path'] = 'three_lane_runner.py'
            item['content'] = (HERE / 'three_lane_runner.py').read_text()
        elif item['path'].startswith('tests/'):
            item['path'] = 'tests/test_three_lane_runner_config.py'
            item['content'] = (HERE / item['path']).read_text()
    construction['files'] = list({item['path']: item for item in construction['files']}.values())
    construction['files'].append({'path': 'right_half_three_lane.py',
                                  'content': (HERE / 'right_half_three_lane.py').read_text()})
    construction['files'].append({'path': 'tests/test_right_half_three_lane.py',
                                  'content': (HERE / 'tests/test_right_half_three_lane.py').read_text()})
    construction['measurement_plan']['original_sources'].append('three-lane lane_inventory in ego_road_frames.jsonl')
    path = HERE / 'construction-three_lane_left.json'
    write(path, construction)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery', 'construction': path.name,
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'right_half_finalizer.py'},
        'candidate_risk': {'status': 'physical', 'reason':
            'Native three-lane map selection, left-half motion, four cameras and applicable lane rule need verification'},
        'candidates': [],
    })
    write(manifest_path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
