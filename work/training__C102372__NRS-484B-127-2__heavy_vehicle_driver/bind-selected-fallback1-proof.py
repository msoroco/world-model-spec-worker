"""Bind tested exact fallback1 receipts for the first selected truck-follow case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_1'
PROOF = HERE / 'selected-proof/probe_1/fallback1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    fallback = next(item for item in entry['candidates'] if item['id'] == 'fallback1')
    receipt = json.loads((PROOF / 'compatibility.json').read_text())
    if (receipt.get('passed'), receipt.get('case_id'), receipt.get('candidate_id'),
            receipt.get('construction_sha256'), receipt.get('runtime_manifest_sha256')) != (
            True, CASE, 'fallback1', fallback['construction_sha256'], manifest['runtime_manifest_sha256']):
        raise ValueError('Fallback receipt does not bind exact construction and runtime')
    if receipt['log_sha256'] != sha(PROOF / 'analysis.log') or receipt['negative_log_sha256'] != sha(PROOF / 'negative.log'):
        raise ValueError('Fallback source-bound logs changed')
    saved = json.loads((PROOF / 'processing.json').read_text())
    if (saved.get('passed'), saved.get('recorded_only'), saved.get('candidate_id'),
            saved.get('timestamp_joins', {}).get('frames'), saved.get('originals_preserved')) != (
            True, True, 'fallback1', 600, True):
        raise ValueError('Fallback recorded-only saved proof incomplete')
    fallback['offline'] = {
        'command': f'{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py offline '
                   f'--manifest {path} --case {CASE} --candidate fallback1 '
                   f'--output {ROOT}/.runtime-work/c102372-selected-probe1-fallback1-offline-v7 '
                   f'--python {ROOT}/.venv-cpu/bin/python',
        'exit_code': 0, 'construction_sha256': fallback['construction_sha256'],
        'log': 'selected-proof/probe_1/fallback1/offline.log',
        'log_sha256': sha(PROOF / 'offline.log')}
    fallback['compatibility'] = {
        'receipt': 'selected-proof/probe_1/fallback1/compatibility.json',
        'sha256': sha(PROOF / 'compatibility.json'),
        'log': 'selected-proof/probe_1/fallback1/analysis.log',
        'negative_log': 'selected-proof/probe_1/fallback1/negative.log'}
    fallback['saved_processing'] = {
        'receipt': 'selected-proof/probe_1/fallback1/processing.json',
        'sha256': sha(PROOF / 'processing.json')}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'candidate_id': 'fallback1',
                      'compatibility_sha256': fallback['compatibility']['sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
