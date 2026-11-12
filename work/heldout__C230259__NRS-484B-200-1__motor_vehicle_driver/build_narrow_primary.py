"""Construct the exact C230259 narrow-road left-half Native capture package."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__narrow_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    construction = json.loads((HERE / 'construction-baseline_left.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'narrow_runner.py'
    construction['mechanisms']['route'] = ('connected measured narrow two-way Native route '
                                           'with original lane widths at or below a 6.5 m construction screen')
    construction['mechanisms']['control'] = ('bounded left-half route feedback; '
                                             'legal width sufficiency undecided')
    construction['mechanisms']['construction_status'] = 'exact_narrow_primary_offline_pending'
    construction['static_checks'] = [
        'Exact C230259 narrow-road-left identity, 80 original ticks at 20 Hz',
        'Two adjacent opposing Native driving lanes with combined width at or below 6.5 m',
        'Original road/body widths and full-body geometry with four FFV1 cameras',
    ]
    construction['termination_rules'] = [
        'Stop after 80 original ticks',
        'Fail on missing lane, changed width/direction, source frame or camera',
        'Close encoders and restore world settings',
    ]
    construction['recording_description']['limitations'].append(
        'Narrow-road width is original Native map readback; legal sufficiency needs separate review.')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['case']['recording_description'] = construction['recording_description']
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            item['path'] = 'narrow_runner.py'
            item['content'] = (HERE / 'narrow_runner.py').read_text()
        elif item['path'].startswith('tests/'):
            item['path'] = 'tests/test_narrow_runner_config.py'
            item['content'] = (HERE / item['path']).read_text()
    construction['files'] = list({item['path']: item for item in construction['files']}.values())
    construction['files'].append({'path': 'right_half_narrow.py',
                                  'content': (HERE / 'right_half_narrow.py').read_text()})
    construction['files'].append({'path': 'tests/test_right_half_narrow.py',
                                  'content': (HERE / 'tests/test_right_half_narrow.py').read_text()})
    construction['measurement_plan']['original_sources'].append('original road and body widths in ego_road_frames.jsonl and narrow_setup')
    path = HERE / 'construction-narrow_left.json'
    write(path, construction)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery', 'construction': path.name,
        'construction_sha256': sha(path),
        'measurement_procedure': {'entrypoint': 'right_half_finalizer.py'},
        'candidate_risk': {'status': 'physical', 'reason':
            'Native narrow-road map selection, measured width, left-half motion, four cameras and legal sufficiency need verification'},
        'candidates': [],
    })
    write(manifest_path, manifest)
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
