"""Construct the exact C230259 one-way left-half Native capture package."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__one_way_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    construction = json.loads((HERE / 'construction-baseline_left.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'one_way_runner.py'
    construction['mechanisms']['route'] = ('connected two-driving-lane Native route '
                                           'with both lanes outbound and a source-observed sign actor')
    construction['mechanisms']['control'] = ('bounded left-half outer-lane feedback; '
                                             'designation and posting authority undecided')
    construction['mechanisms']['construction_status'] = 'exact_one_way_primary_offline_pending'
    construction['static_checks'] = [
        'Exact C230259 one-way-left identity, 80 original ticks at 20 Hz',
        'Two distinct joined same-direction Native driving lanes and one posted-sign actor',
        'Original lane/sign inventory, full body/road geometry and four FFV1 source cameras',
    ]
    construction['termination_rules'] = [
        'Stop after 80 original ticks',
        'Fail on missing lane/sign actor, changed direction, source frame or camera',
        'Close encoders and restore world settings',
    ]
    construction['recording_description']['limitations'].append(
        'One-way inventory is original Native map readback; official road designation and posting authority need separate review.')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['case']['recording_description'] = construction['recording_description']
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['path'] = 'one_way_runner.py'
            item['content'] = (HERE / 'one_way_runner.py').read_text()
        elif item['path'].startswith('tests/'):
            item['path'] = 'tests/test_one_way_runner_config.py'
            item['content'] = (HERE / item['path']).read_text()
    construction['files'] = list({item['path']: item for item in construction['files']}.values())
    construction['files'].append({'path': 'right_half_one_way.py',
                                  'content': (HERE / 'right_half_one_way.py').read_text()})
    construction['files'].append({'path': 'tests/test_right_half_one_way.py',
                                  'content': (HERE / 'tests/test_right_half_one_way.py').read_text()})
    construction['measurement_plan']['original_sources'].extend(['one-way lane_inventory in ego_road_frames.jsonl', 'one_way_sign.jsonl'])
    path = HERE / 'construction-one_way_left.json'
    write(path, construction)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery', 'construction': path.name,
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'right_half_finalizer.py'},
        'candidate_risk': {'status': 'physical', 'reason':
            'Native same-direction map selection, sign visibility, left-half motion, four cameras, official designation and posting authority need verification'},
        'candidates': [],
    })
    write(manifest_path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
