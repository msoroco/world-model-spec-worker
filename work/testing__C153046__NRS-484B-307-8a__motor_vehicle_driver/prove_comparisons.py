"""Exercise five exact pair audits on synthetic saved attempts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / 'selected_comparison.py'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work/c153046-nov25d/tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c153046-nov25d/output'))
    receipts = []
    for pair in plan['comparisons']:
        ident = pair['comparison_id']
        paths = [REPO / '.runtime-work' / ('c153046-saved-proof-' +
                 case.removeprefix(ROOT.name + '__') + '-v8') / 'v0001/analysis'
                 for case in pair['case_ids']]
        command = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT), '--comparison', ident,
                   '--left', str(paths[0]), '--right', str(paths[1])]
        positive = subprocess.run(command + ['--allow-diagnostic'], cwd=REPO, env=env,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        negative = subprocess.run(command, cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        positive_log = ROOT / ('cpu-selected-comparison-' + ident + '.log')
        negative_log = ROOT / ('cpu-selected-comparison-negative-' + ident + '.log')
        positive_log.write_text(positive.stdout.rstrip() + '\n')
        negative_log.write_text(negative.stdout.rstrip() + '\n')
        expected = 'synthetic source cannot establish original comparison'
        if positive.returncode != 0 or negative.returncode == 0 or expected not in negative.stdout:
            raise ValueError('selected comparison diagnostic/rejection failed: ' + ident)
        receipts.append({'comparison_id': ident, 'case_ids': pair['case_ids'],
                         'auditor': SCRIPT.name, 'auditor_sha256': sha(SCRIPT),
                         'positive_command': ' '.join(command + ['--allow-diagnostic']),
                         'positive_exit_code': 0, 'positive_log': positive_log.name,
                         'positive_log_sha256': sha(positive_log),
                         'negative_command': ' '.join(command),
                         'negative_exit_code': negative.returncode,
                         'negative_expected_error': expected,
                         'negative_log': negative_log.name,
                         'negative_log_sha256': sha(negative_log),
                         'diagnostic_fixture': True,
                         'realized_difference_claimed': False})
        print('comparison diagnostic/rejection passed:', ident, flush=True)
    (ROOT / 'cpu-comparison-diagnostics.json').write_text(
        json.dumps({'format': 'worker-comparison-diagnostics', 'comparisons': receipts,
                    'diagnostic_fixture': True, 'realized_difference_claimed': False},
                   indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
