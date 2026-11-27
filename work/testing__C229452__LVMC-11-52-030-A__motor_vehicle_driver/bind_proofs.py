"""Attach already executed exact candidate proof receipts to the manifest."""

import hashlib
import json
from pathlib import Path

from red_curb import CASES
from run_proofs import MANIFEST, PYTHON, ROOT, RUNTIME, SCRATCH, LIBRARY, VALIDATOR


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for case, entry in zip(CASES, manifest['cases']):
        assert entry['case_id'].endswith('__' + case.name)
        for candidate in ('primary', 'fallback1'):
            item = entry if candidate == 'primary' else entry['candidates'][0]
            short = case.name + '-' + candidate
            folder = SCRATCH / short
            offline = ROOT / ('cpu-offline-' + short + '.log')
            detail = ROOT / ('cpu-offline-detail-' + short + '.log')
            receipt = ROOT / ('cpu-compatibility-' + short + '.json')
            analysis = ROOT / ('cpu-compatibility-analysis-' + short + '.log')
            negative = ROOT / ('cpu-compatibility-negative-' + short + '.log')
            compat = json.loads(receipt.read_text())
            assert compat['passed'] and compat['case_id'] == entry['case_id']
            assert compat['candidate_id'] == candidate
            assert compat['construction_sha256'] == item['construction_sha256']
            assert compat['log_sha256'] == sha(analysis)
            assert compat['negative_log_sha256'] == sha(negative)
            assert 'passed' in offline.read_text().lower() or offline.stat().st_size > 0
            assert detail.stat().st_size > 0
            offline_command = [str(PYTHON), str(RUNTIME), 'offline',
                               '--manifest', str(MANIFEST), '--case', entry['case_id'],
                               '--candidate', candidate, '--output', str(folder / 'offline'),
                               '--python', str(PYTHON)]
            compatibility_command = [str(PYTHON), str(RUNTIME), 'compatibility',
                                     '--manifest', str(MANIFEST), '--case', entry['case_id'],
                                     '--candidate', candidate, '--output', str(folder / 'compat'),
                                     '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
            item['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                               'construction_sha256': item['construction_sha256'],
                               'log': detail.name, 'log_sha256': sha(detail)}
            item['compatibility'] = {'command': ' '.join(compatibility_command),
                                     'receipt': receipt.name, 'sha256': sha(receipt),
                                     'log': analysis.name, 'negative_log': negative.name}
            if candidate == 'primary':
                item['negative'] = {'log': negative.name}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
