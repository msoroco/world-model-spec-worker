"""Bind exact tested CPU receipts for a selected truck delivery case."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, choices=(
        'two_lane_exception', 'passing_hold', 'passing_overtake',
        'conditions_steady', 'conditions_lead_brake'))
    suffix = parser.parse_args().case
    case_id = HERE.name + '__' + suffix
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == case_id)
    recipe_path = HERE / 'selected-fixture' / suffix / 'recipe.json'
    for candidate_id in ('primary', 'fallback1'):
        proof = HERE / 'selected-proof' / suffix / candidate_id
        target = entry if candidate_id == 'primary' else next(
            row for row in entry['candidates'] if row['id'] == candidate_id)
        receipt = json.loads((proof / 'compatibility.json').read_text())
        if (receipt.get('passed'), receipt.get('case_id'),
                receipt.get('candidate_id'), receipt.get('construction_sha256'),
                receipt.get('runtime_manifest_sha256')) != (
                True, case_id, candidate_id, target['construction_sha256'],
                manifest['runtime_manifest_sha256']):
            raise ValueError('Compatibility receipt does not bind selected construction')
        if (receipt['log_sha256'] != sha(proof / 'analysis.log') or
                receipt['negative_log_sha256'] != sha(proof / 'negative.log') or
                receipt['fixture_recipe_sha256'] != sha(recipe_path)):
            raise ValueError('Compatibility logs or fixture differ from tested receipt')
        saved = json.loads((proof / 'processing.json').read_text())
        if (saved.get('passed'), saved.get('recorded_only'),
                saved.get('candidate_id'), saved.get('originals_preserved'),
                saved.get('timestamp_joins', {}).get('frames')) != (
                True, True, candidate_id, True, 600):
            raise ValueError('Recorded-only saved source processing incomplete')
        stem = ('two-lane' if suffix == 'two_lane_exception' else suffix)
        offline_output = (f'c102372-selected-{stem}-offline-v1' if suffix ==
                          'two_lane_exception' and candidate_id == 'primary' else
                          f'c102372-selected-{stem}-fallback1-offline-v1' if suffix ==
                          'two_lane_exception' else
                          f'c102372-selected-{stem}-{candidate_id}-offline-v3' if suffix ==
                          'passing_overtake' else
                          f'c102372-selected-{stem}-{candidate_id}-offline-v1')
        candidate_arg = '' if candidate_id == 'primary' else ' --candidate fallback1'
        target['offline'] = {
            'command': f'{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py offline '
                       f'--manifest {manifest_path} --case {case_id}{candidate_arg} '
                       f'--output {ROOT}/.runtime-work/{offline_output} '
                       f'--python {ROOT}/.venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': target['construction_sha256'],
            'log': f'selected-proof/{suffix}/{candidate_id}/offline.log',
            'log_sha256': sha(proof / 'offline.log')}
        target['compatibility'] = {
            'receipt': f'selected-proof/{suffix}/{candidate_id}/compatibility.json',
            'sha256': sha(proof / 'compatibility.json'),
            'log': f'selected-proof/{suffix}/{candidate_id}/analysis.log',
            'negative_log': f'selected-proof/{suffix}/{candidate_id}/negative.log'}
        target['saved_processing'] = {
            'receipt': f'selected-proof/{suffix}/{candidate_id}/processing.json',
            'sha256': sha(proof / 'processing.json')}
        if candidate_id == 'primary':
            feedback = json.loads((proof / 'saved-negative-feedback.json').read_text())
            if ('Missing required source: native_samples.jsonl' not in feedback.get('error', '')
                    or feedback.get('native_replay_requested') is not False):
                raise ValueError('Missing-source saved negative did not reject')
            saved_command = (f'{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py process-saved '
                             f'--manifest {manifest_path} --case {case_id} --attempt $ATTEMPT '
                             f'--output $SAVED_OUTPUT --library {ROOT}/runtime/library '
                             f'--validator {ROOT}/.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck')
            entry['negative'] = {'log': f'selected-proof/{suffix}/primary/negative.log'}
            entry['post_capture'] = {
                'command': saved_command, 'feedback_command': saved_command,
                'recorded_only': True, 'test_exit_code': 0,
                'test_log': f'selected-proof/{suffix}/primary/saved.log',
                'test_log_sha256': sha(proof / 'saved.log')}
            target['saved_processing']['negative_log'] = f'selected-proof/{suffix}/primary/saved-negative.log'
            target['saved_processing']['negative_log_sha256'] = sha(proof / 'saved-negative.log')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'selected_candidates': 2}, sort_keys=True))


if __name__ == '__main__':
    bind()
