"""Bind exact towing diagnostic fallback and physical proof hashes."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / 'towing-diagnostic-manifest.json'


def sha(relative):
    return hashlib.sha256((PACKAGE / relative).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest['cases'][0]
    fallback = entry['candidates'][0]
    if fallback['id'] != 'fallback1':
        raise ValueError('Exact fallback1 required')
    offline = 'cases/towing-fallback1-offline.log'
    fallback['offline'] = {
        'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/' + PACKAGE.name + '/towing-diagnostic-manifest.json --case ' + entry['case_id'] + ' --candidate fallback1 --output .runtime-work/c160013-towing-fallback1-offline --python $PWD/.venv-cpu/bin/python',
        'construction_sha256': fallback['construction_sha256'],
        'exit_code': 0, 'log': offline, 'log_sha256': sha(offline)}
    receipt = 'cases/towing-fallback1-compatibility.json'
    fallback['compatibility'] = {
        'receipt': receipt, 'sha256': sha(receipt),
        'log': 'cases/towing-fallback1-compatibility-analysis.log',
        'negative_log': 'cases/towing-fallback1-compatibility-negative.log'}
    physical = 'cases/towing-physical-preparation.json'
    entry['physical_preparation'] = {'receipt': physical, 'sha256': sha(physical)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': entry['case_id'],
                      'fallback1_sha256': fallback['construction_sha256'],
                      'compatibility_sha256': sha(receipt),
                      'physical_sha256': sha(physical)}, sort_keys=True))


if __name__ == '__main__':
    main()
