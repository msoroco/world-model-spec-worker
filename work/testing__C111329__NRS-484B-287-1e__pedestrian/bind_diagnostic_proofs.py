"""Bind tested diagnostic receipts without selecting physical delivery readiness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.draft.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        folder = HERE / 'cases' / suffix
        receipt = folder / 'compatibility.json'
        analysis = folder / 'analysis-positive.log'
        negative = folder / 'negative-analysis.log'
        if not all(path.is_file() for path in (receipt, analysis, negative)):
            raise ValueError('primary current-runtime receipt missing: ' + suffix)
        checked = json.loads(receipt.read_text())
        if (checked['case_id'] != case or checked['candidate_id'] != 'primary'
                or checked['construction_sha256'] != entry['construction_sha256']
                or checked['log_sha256'] != sha(analysis)
                or checked['negative_log_sha256'] != sha(negative)):
            raise ValueError('primary current-runtime receipt differs: ' + suffix)
        entry['compatibility'] = {
            'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt),
            'log': str(analysis.relative_to(HERE)),
            'negative_log': str(negative.relative_to(HERE)),
            'command': '.venv-cpu/bin/python runtime.py compatibility --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + case
                       + ' --output .runtime-work/c111329-compat-' + suffix
                       + '-semantic-v1 --library runtime/library --validator '
                       + '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck',
            'exit_code': 0}
        entry['negative'] = {'log': str(negative.relative_to(HERE)),
                             'expected_error': 'Missing required source: diagonal-source.json',
                             'exit_code': 1}
        offline = HERE / ('nov25-offline-' + suffix + '.log')
        entry['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                            + str(MANIFEST.relative_to(REPO)) + ' --case ' + case
                            + ' --output .runtime-work/c111329-offline-' + suffix
                            + '-v2 --python "$PWD/.venv-cpu/bin/python"',
                            'exit_code': 0, 'log': offline.name,
                            'log_sha256': sha(offline),
                            'construction_sha256': entry['construction_sha256']}
        saved = HERE / ('nov25-saved-' + suffix + '.log')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + case
                       + ' --attempt .runtime-work/c111329-saved-source-' + suffix
                       + '-v3 --output .runtime-work/c111329-saved-' + suffix
                       + '-v3 --library runtime/library --validator '
                       + '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck',
            'test_exit_code': 0, 'test_log': saved.name,
            'test_log_sha256': sha(saved)}
        fallback = entry['candidates'][0]
        source = REPO / '.runtime-work' / ('c111329-fallback-compat-' + suffix + '-v1')
        targets = ((source / 'compatibility.json', folder / 'fallback1-receipt.json'),
                   (source / 'compatibility-analysis.log', folder / 'fallback1-positive.log'),
                   (source / 'negative-analysis.log', folder / 'fallback1-negative.log'))
        for original, target in targets:
            target.write_bytes(original.read_bytes())
        proof = json.loads((folder / 'fallback1-receipt.json').read_text())
        if (proof['case_id'] != case or proof['candidate_id'] != 'fallback1'
                or proof['construction_sha256'] != fallback['construction_sha256']
                or proof['log_sha256'] != sha(folder / 'fallback1-positive.log')
                or proof['negative_log_sha256'] != sha(folder / 'fallback1-negative.log')):
            raise ValueError('fallback current-runtime receipt differs: ' + suffix)
        fallback_log = HERE / ('nov25-fallback-offline-' + suffix + '.log')
        fallback['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + case
                       + ' --candidate fallback1 --output '
                       + '.runtime-work/c111329-fallback-offline-' + suffix
                       + '-v1 --python "$PWD/.venv-cpu/bin/python"',
            'exit_code': 0, 'log': fallback_log.name,
            'log_sha256': sha(fallback_log),
            'construction_sha256': fallback['construction_sha256']}
        fallback['compatibility'] = {
            'command': '.venv-cpu/bin/python runtime.py compatibility --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + case
                       + ' --candidate fallback1 --output '
                       + '.runtime-work/c111329-fallback-compat-' + suffix
                       + '-v1 --library runtime/library --validator '
                       + '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck',
            'exit_code': 0,
            'receipt': str((folder / 'fallback1-receipt.json').relative_to(HERE)),
            'sha256': sha(folder / 'fallback1-receipt.json'),
            'log': str((folder / 'fallback1-positive.log').relative_to(HERE)),
            'negative_log': str((folder / 'fallback1-negative.log').relative_to(HERE))}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print('bound', bind(), 'source-gated diagnostic primary and fallback proofs')
