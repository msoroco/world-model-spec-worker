"""Rebind exact primary constructions after shared runner/finalizer changes."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases_manifest = root / 'construction-cases-manifest.json'
compat_manifest = root / 'probe-compatibility-manifest.json'
cases = json.loads(cases_manifest.read_text())
compat = json.loads(compat_manifest.read_text())
by_id = {entry['case_id']: entry for entry in compat['cases']}
runner = (root / 'native_exposure_cases.py').read_text().replace(
    "default='cases/slow_person_exposure.json'", "default='config.json'")
finalizer = (root / 'endangerment_finalizer.py').read_text()
finalizer_test = (root / 'tests/test_endangerment_finalizer.py').read_text()
case_setup = (root / 'exposure_case_setup.py').read_text()
case_setup_test = (root / 'tests/test_exposure_case_setup.py').read_text()
for entry in cases['cases']:
    path = root / entry['construction']
    construction = json.loads(path.read_text())
    files = {item['path']: item for item in construction['files']}
    files['native_exposure_cases.py']['content'] = runner
    files['endangerment_finalizer.py']['content'] = finalizer
    files['tests/test_endangerment_finalizer.py']['content'] = finalizer_test
    files['exposure_case_setup.py']['content'] = case_setup
    files['tests/test_exposure_case_setup.py']['content'] = case_setup_test
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    config_path = root / 'cases' / (suffix + '.json')
    config = json.loads(config_path.read_text())
    config['duration_s'] = 8
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    files['config.json']['content'] = config_path.read_text()
    if 'runner.py' not in files:
        construction['files'].append({'path': 'runner.py', 'content': runner})
    else:
        files['runner.py']['content'] = runner
    path.write_text(json.dumps(construction, indent=2) + '\n')
    entry['construction_sha256'] = sha(path)
    by_id[entry['case_id']]['construction_sha256'] = sha(path)
cases_manifest.write_text(json.dumps(cases, indent=2) + '\n')
compat_manifest.write_text(json.dumps(compat, indent=2) + '\n')
print('Rebound', len(cases['cases']), 'primary constructions')
