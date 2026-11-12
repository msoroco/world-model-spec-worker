"""Bind the exact left-approach CPU receipt without claiming Native acceptance."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__source_verified_other_left_near_time'
FOLDER = ROOT / 'cases/source_verified_other_left_near_time'
ATTEMPT = REPO / '.runtime-work/c125714-left-compat-v3'
SAVED = REPO / '.runtime-work/c125714-left-saved-v3/v0001/processing.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == CASE)
    receipt = json.loads((ATTEMPT / 'compatibility.json').read_text())
    saved = json.loads(SAVED.read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != CASE
            or receipt.get('construction_sha256') != entry['construction_sha256']
            or saved.get('passed') is not True or saved.get('recorded_only') is not True
            or saved.get('originals_preserved') is not True
            or saved.get('physical_acceptance_claimed') is not False
            or saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('Exact left CPU proof is incomplete')
    copies = {'compatibility.json': 'primary-compatibility-receipt.json',
              'compatibility-analysis.log': 'primary-compatibility-analysis.log',
              'negative-analysis.log': 'primary-negative-analysis.log'}
    for source, target in copies.items():
        shutil.copyfile(ATTEMPT / source, FOLDER / target)
    shutil.copyfile(SAVED, FOLDER / 'primary-processing-receipt.json')
    offline = FOLDER / 'primary-offline.log'
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {CASE} --output .runtime-work/c125714-left-offline-v3',
        'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
        'log': str(offline.relative_to(ROOT)), 'log_sha256': sha(offline)}
    path = FOLDER / 'primary-compatibility-receipt.json'
    entry['compatibility'] = {'receipt': str(path.relative_to(ROOT)), 'sha256': sha(path),
                              'log': str((FOLDER / 'primary-compatibility-analysis.log').relative_to(ROOT))}
    entry['negative'] = {'log': str((FOLDER / 'primary-negative-analysis.log').relative_to(ROOT))}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'offline': True, 'compatibility': True,
                      'negative_source': receipt['negative_removed'],
                      'recorded_only_saved': True, 'physical_acceptance_claimed': False,
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
