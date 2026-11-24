"""Attach tested current-runtime probe_2 primary receipts to the exact manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_2'
PROOF = HERE / 'selected-proof/probe_2/primary'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    receipt = json.loads((PROOF / 'compatibility.json').read_text())
    if (receipt.get('passed'), receipt.get('case_id'), receipt.get('candidate_id'),
            receipt.get('construction_sha256'), receipt.get('runtime_manifest_sha256')) != (
            True, CASE, 'primary', entry['construction_sha256'], manifest['runtime_manifest_sha256']):
        raise ValueError('Selected proof does not bind exact construction and runtime')
    if receipt['log_sha256'] != sha(PROOF / 'analysis.log'):
        raise ValueError('Selected analysis log differs')
    if receipt['negative_log_sha256'] != sha(PROOF / 'negative.log'):
        raise ValueError('Selected negative log differs')
    if receipt['fixture_recipe_sha256'] != sha(HERE / 'selected-fixture/probe_2/recipe.json'):
        raise ValueError('Selected fixture changed')
    entry['offline'] = {
        'command': f'{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py offline '
                   f'--manifest {path} --case {CASE} '
                   f'--output {ROOT}/.runtime-work/c102372-selected-probe2-offline-v1 '
                   f'--python {ROOT}/.venv-cpu/bin/python',
        'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
        'log': 'selected-proof/probe_2/primary/offline.log',
        'log_sha256': sha(PROOF / 'offline.log')}
    entry['compatibility'] = {
        'receipt': 'selected-proof/probe_2/primary/compatibility.json',
        'sha256': sha(PROOF / 'compatibility.json'),
        'log': 'selected-proof/probe_2/primary/analysis.log',
        'negative_log': 'selected-proof/probe_2/primary/negative.log'}
    entry['negative'] = {'log': 'selected-proof/probe_2/primary/negative.log'}
    saved = json.loads((PROOF / 'processing.json').read_text())
    if (saved.get('passed'), saved.get('recorded_only'), saved.get('candidate_id'),
            saved.get('timestamp_joins', {}).get('frames'), saved.get('originals_preserved')) != (
            True, True, 'primary', 600, True):
        raise ValueError('Selected saved processing lacks original 600-frame proof')
    feedback = json.loads((PROOF / 'saved-negative-feedback.json').read_text())
    if ('Missing required source: native_samples.jsonl' not in feedback.get('error', '')
            or feedback.get('native_replay_requested') is not False):
        raise ValueError('Selected saved negative did not reject missing original source')
    saved_command = (f'{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py process-saved '
                     f'--manifest {path} --case {CASE} --attempt $ATTEMPT '
                     f'--output $SAVED_OUTPUT --library {ROOT}/runtime/library '
                     f'--validator {ROOT}/.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck')
    entry['post_capture'] = {
        'command': saved_command, 'feedback_command': saved_command,
        'recorded_only': True, 'test_exit_code': 0,
        'test_log': 'selected-proof/probe_2/primary/saved.log',
        'test_log_sha256': sha(PROOF / 'saved.log')}
    entry['saved_processing'] = {
        'receipt': 'selected-proof/probe_2/primary/processing.json',
        'sha256': sha(PROOF / 'processing.json'),
        'negative_log': 'selected-proof/probe_2/primary/saved-negative.log',
        'negative_log_sha256': sha(PROOF / 'saved-negative.log')}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'compatibility_sha256':
                      entry['compatibility']['sha256'],
                      'offline_log_sha256': entry['offline']['log_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
