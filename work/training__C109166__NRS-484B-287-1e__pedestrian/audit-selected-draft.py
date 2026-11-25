"""Independent exact candidate and controlled-variable construction audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fail(message):
    raise ValueError(message)


def read_bundle(suffix, candidate):
    path = HERE / 'cases' / suffix / candidate / 'construction.json'
    data = json.loads(path.read_text())
    files = {item['path']: item['content'] for item in data['files']}
    config = json.loads(files['config.json'])
    if files['runner.py'] != (HERE / 'native/capture_runner.py').read_text():
        fail('Native runner changed in exact bundle')
    if files['finalize.py'] != (HERE / 'native/finalize.py').read_text():
        fail('Saved finalizer changed in exact bundle')
    return data, config, sha(path)


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if [case['case_id'] for case in manifest['cases']] != [BASE+'__controlled_1', BASE+'__controlled_2']:
        fail('selected exact cases differ')
    configs = {}
    bundles = []
    for entry, suffix in zip(manifest['cases'], ('controlled_1', 'controlled_2')):
        for candidate in ('primary', 'fallback1'):
            data, config, digest = read_bundle(suffix, candidate)
            item = entry if candidate == 'primary' else entry['candidates'][0]
            if digest != item['construction_sha256'] or data['case_id'] != entry['case_id']:
                fail('selected construction hash or case differs')
            log = HERE / f"selected-{suffix[-1]}-{candidate}-offline.log"
            if not log.is_file() or 'offline_passed' not in log.read_text():
                fail('exact offline receipt missing: ' + suffix + '/' + candidate)
            configs[suffix, candidate] = config
            bundles.append({'case_id': data['case_id'], 'candidate': candidate,
                            'construction_sha256': digest, 'offline_log_sha256': sha(log)})
    for suffix in ('controlled_1', 'controlled_2'):
        first = dict(configs[suffix, 'primary'])
        second = dict(configs[suffix, 'fallback1'])
        for row in (first, second):
            row.pop('candidate_id')
            row.pop('driver_reference_height_m')
        if first != second:
            fail('fallback changed condition beyond device camera fov')
    left = dict(configs['controlled_1', 'primary'])
    right = dict(configs['controlled_2', 'primary'])
    for row in (left, right):
        row.pop('case_id')
        row.pop('selected_case_id')
        row.pop('case_suffix')
        row['case'] = {key: value for key, value in row['case'].items() if key != 'case_id'}
    if left != right:
        fail('controlled pair changed construction outside requested device program')
    result = {'format': 'c109166-selected-draft-candidate-audit-v1',
              'passed': True, 'bundles': bundles, 'controlled_variable':
              'governing diagonal device requested instruction on first-entry frames',
            'fallback_changed_knobs': ['driver_reference_height_m: 3.0 to 2.2'],
              'official_status_verified': False, 'physical_completion_verified': False,
              'delivery_ready': False}
    target = HERE / 'selected-draft-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'bundles': len(bundles), 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
