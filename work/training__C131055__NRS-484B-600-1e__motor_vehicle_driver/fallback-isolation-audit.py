"""Check three exact cases apply one shared gain change and preserve source variables."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = 'throttle = min(1.0, max(0.0, (target - speed) * .35))'
NEW = 'throttle = min(1.0, max(0.0, (target - speed) * .55))'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


manifest = json.loads((HERE / 'execution-manifest.json').read_text())
hashes = {}
for entry in manifest['cases']:
    fallback = next((item for item in entry['candidates']
                     if item['id'] == 'fallback1'), None)
    require(fallback is not None, 'Missing shared fallback')
    primary_path = HERE / entry['construction']
    fallback_path = HERE / fallback['construction']
    require(sha(primary_path) == entry['construction_sha256'] and
            sha(fallback_path) == fallback['construction_sha256'],
            'Construction binding differs')
    primary = json.loads(primary_path.read_text())
    alternate = json.loads(fallback_path.read_text())
    for field in ('actor', 'case_id', 'cell_id', 'law_id', 'entrypoint',
                  'measurement_plan', 'mechanisms', 'recording_description',
                  'static_checks', 'termination_rules'):
        require(primary[field] == alternate[field],
                'Fallback changed fixed field: ' + field)
    primary_files = {item['path']: item['content'] for item in primary['files']}
    alternate_files = {item['path']: item['content'] for item in alternate['files']}
    require(primary_files.keys() == alternate_files.keys(),
            'Fallback file set differs')
    for path in primary_files:
        if path == 'runner.py':
            require(primary_files[path].count(OLD) == 1 and
                    alternate_files[path] == primary_files[path].replace(OLD, NEW),
                    'Fallback runner differs beyond shared gain')
        elif path == 'config.json':
            a = json.loads(primary_files[path])
            b = json.loads(alternate_files[path])
            b['status'] = a['status']
            b['candidate_id'] = a['candidate_id']
            require(a == b, 'Fallback config changed comparison variable')
        else:
            require(primary_files[path] == alternate_files[path],
                    'Fallback changed fixed file: ' + path)
    hashes[entry['case_id']] = {'primary': sha(primary_path),
                                'fallback1': sha(fallback_path)}
result = {'format': 'worker-fallback-isolation-audit', 'passed': True,
          'shared_changed_knob': 'throttle gain 0.35 to 0.55',
          'fixed_conditions_verified': ['law', 'cell', 'actor', 'case',
                                         'required source', 'recording',
                                         'camera plan', 'duration',
                                         'comparison speed request'],
          'construction_sha256': hashes,
          'physical_or_legal_acceptance': False}
path = HERE / 'fallback-isolation-v3-receipt.json'
require(not path.exists(), 'Retain previous isolation receipt')
path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
