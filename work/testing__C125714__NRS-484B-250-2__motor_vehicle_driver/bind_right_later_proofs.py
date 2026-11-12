"""Bind the later-entry exact CPU receipts to the partial manifest."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__source_verified_other_right_later'
FOLDER = ROOT / 'cases/source_verified_other_right_later'
ATTEMPT = REPO / '.runtime-work/c125714-later-compat-v2'
SAVED = REPO / '.runtime-work/c125714-later-saved-v2/v0001/processing.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == CASE)
    proof = json.loads((ATTEMPT / 'compatibility.json').read_text())
    saved = json.loads(SAVED.read_text())
    if (proof.get('passed') is not True or proof.get('case_id') != CASE
            or proof.get('construction_sha256') != entry['construction_sha256']
            or saved.get('passed') is not True or saved.get('recorded_only') is not True
            or saved.get('originals_preserved') is not True
            or saved.get('physical_acceptance_claimed') is not False
            or saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('Later-entry exact CPU proof incomplete')
    for source, target in (('compatibility.json', 'primary-compatibility-receipt.json'),
                           ('compatibility-analysis.log', 'primary-compatibility-analysis.log'),
                           ('negative-analysis.log', 'primary-negative-analysis.log')):
        shutil.copyfile(ATTEMPT / source, FOLDER / target)
    shutil.copyfile(SAVED, FOLDER / 'primary-processing-receipt.json')
    offline = FOLDER / 'primary-offline.log'
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {CASE} --output .runtime-work/c125714-later-offline-v2',
        'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
        'log': str(offline.relative_to(ROOT)), 'log_sha256': sha(offline)}
    receipt = FOLDER / 'primary-compatibility-receipt.json'
    entry['compatibility'] = {'receipt': str(receipt.relative_to(ROOT)),
                              'sha256': sha(receipt),
                              'log': str((FOLDER / 'primary-compatibility-analysis.log').relative_to(ROOT))}
    entry['negative'] = {'log': str((FOLDER / 'primary-negative-analysis.log').relative_to(ROOT))}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'offline': True, 'compatibility': True,
                      'recorded_only_saved': True, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
