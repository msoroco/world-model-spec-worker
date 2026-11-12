"""Bind current offline, compatibility, negative, and saved receipts for three fallbacks."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FOLDER = ROOT / 'cases/source_verified_other_right_near_time'
CASE = ROOT.name + '__source_verified_other_right_near_time'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    if len(entry['candidates']) != 3:
        raise ValueError('Three primary-case fallback constructions required')
    for index, candidate in enumerate(entry['candidates'], 1):
        ident = f'fallback{index}'
        if candidate['id'] != ident or sha(ROOT / candidate['construction']) != candidate['construction_sha256']:
            raise ValueError('Fallback construction changed: ' + ident)
        attempt = REPO / f'.runtime-work/c125714-primary-{ident}-compat-v1'
        saved_path = REPO / f'.runtime-work/c125714-primary-{ident}-saved-v1/v0001/processing.json'
        proof = json.loads((attempt / 'compatibility.json').read_text())
        saved = json.loads(saved_path.read_text())
        if (proof.get('passed') is not True or proof.get('case_id') != CASE or
                proof.get('candidate_id') != ident or
                proof.get('construction_sha256') != candidate['construction_sha256'] or
                saved.get('passed') is not True or saved.get('candidate_id') != ident or
                saved.get('recorded_only') is not True or
                saved.get('originals_preserved') is not True or
                saved.get('physical_acceptance_claimed') is not False or
                saved.get('legal_acceptance_claimed') is not False):
            raise ValueError('Fallback proof incomplete: ' + ident)
        for source, suffix in (('compatibility.json', 'compatibility-receipt.json'),
                               ('compatibility-analysis.log', 'compatibility-analysis.log'),
                               ('negative-analysis.log', 'negative-analysis.log')):
            shutil.copyfile(attempt / source, FOLDER / f'{ident}-{suffix}')
        shutil.copyfile(saved_path, FOLDER / f'{ident}-processing-receipt.json')
        offline_log = FOLDER / f'{ident}-offline.log'
        receipt = FOLDER / f'{ident}-compatibility-receipt.json'
        candidate['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {CASE} --candidate {ident} --output .runtime-work/c125714-primary-{ident}-offline-v1',
            'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
            'log': str(offline_log.relative_to(ROOT)), 'log_sha256': sha(offline_log)}
        candidate['compatibility'] = {
            'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt),
            'log': str((FOLDER / f'{ident}-compatibility-analysis.log').relative_to(ROOT)),
            'negative_log': str((FOLDER / f'{ident}-negative-analysis.log').relative_to(ROOT))}
        candidate['saved_processing'] = {
            'receipt': str((FOLDER / f'{ident}-processing-receipt.json').relative_to(ROOT)),
            'sha256': sha(FOLDER / f'{ident}-processing-receipt.json')}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'fallbacks_bound': 3, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
