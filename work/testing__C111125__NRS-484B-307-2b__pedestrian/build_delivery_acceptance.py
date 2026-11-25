"""Bind independent positive/negative CPU delivery-audit test commands."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c111125-owner'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(command, log):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'output')
    env['TMPDIR'] = str(SCRATCH / 'tmp')
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip() + '\n')
    return result.returncode, result.stdout


def main():
    (SCRATCH / 'tmp').mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'output').mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        attempt = SCRATCH / ('selected-compat-' + suffix + '-delivery-v7')
        compatibility = folder / 'delivery-compatibility-draft.json'
        command = [sys.executable, str(ROOT / 'prove_delivery_acceptance.py'),
                   '--case', case_id, '--attempt', str(attempt),
                   '--receipt', str(compatibility), '--mode', 'positive',
                   '--scratch', str(SCRATCH / 'delivery-audit')]
        log = folder / 'delivery-acceptance-positive.log'
        exit_code, output = call(command, log)
        if exit_code or json.loads(output)['diagnostic_source_audit_passed'] is not True:
            raise ValueError('independent positive audit failed: ' + suffix)
        negative = command.copy()
        negative[negative.index('positive')] = 'negative'
        negative_log = folder / 'delivery-acceptance-negative.log'
        negative_exit, negative_output = call(negative, negative_log)
        expected = 'saved diagnostic source changed: frames.json'
        if negative_exit == 0 or expected not in negative_output:
            raise ValueError('independent negative audit failed: ' + suffix)
        receipt = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'scope': 'CPU source and classifier protocol test only; actual reviewed Native delivery pending',
            'command': ' '.join(command), 'test_exit_code': 0,
            'negative_command': ' '.join(negative),
            'negative_exit_code': negative_exit,
            'negative_expected_error': expected,
            'script': 'prove_delivery_acceptance.py',
            'script_sha256': sha(ROOT / 'prove_delivery_acceptance.py'),
            'audit_module_sha256': sha(ROOT / 'saved_compatibility_audit.py'),
            'test_log': str(log.relative_to(ROOT)), 'test_log_sha256': sha(log),
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': sha(negative_log),
            'reviewed_native_site_accepted': False,
            'physical_acceptance_claimed': False,
        }
        (folder / 'delivery-acceptance.draft.json').write_text(
            json.dumps(receipt, indent=2) + '\n')
        print(f'{suffix}: independent source and classifier audit passed', flush=True)


if __name__ == '__main__':
    main()
