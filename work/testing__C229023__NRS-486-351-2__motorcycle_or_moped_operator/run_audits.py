"""Prove saved-source integrity and exact independent comparisons on CPU."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229023-owner-nov26'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(command, log, expected, text):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    process = subprocess.run(command, cwd=REPO, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
    content = process.stdout.rstrip() + '\n'
    log.write_text(content)
    if process.returncode != expected or text not in content:
        raise ValueError(f'CPU audit differed: {log}: {content[-1200:]}')
    return sha(log)


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    attempts = {}
    delivery = ROOT / 'delivery_audit.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        attempt = (SCRATCH / 'compat-same-lane-primary-v4' if suffix == 'same_lane_pass'
                   else SCRATCH / f'compat-{suffix}-primary-proof')
        require = attempt / 'compatibility.json'
        if not require.is_file():
            raise ValueError('Exact compatibility proof missing: ' + case)
        attempts[case] = attempt
        folder = ROOT / 'cases' / suffix
        positive = [sys.executable, str(delivery), '--attempt', str(attempt), '--case', case]
        negative = positive + ['--require-original']
        positive_log = folder / 'delivery-positive.log'
        negative_log = folder / 'delivery-negative.log'
        positive_sha = run(positive, positive_log, 0, '"native_source": false')
        negative_sha = run(negative, negative_log, 1,
                           'Diagnostic source cannot satisfy original Native delivery')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': delivery.name, 'script_sha256': sha(delivery),
            'command': shlex.join(positive), 'negative_command': shlex.join(negative),
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Diagnostic source cannot satisfy original Native delivery',
            'test_log': str(positive_log.relative_to(ROOT)),
            'test_log_sha256': positive_sha,
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': negative_sha,
            'scope': 'Diagnostic integrity and original-only rejection; original visual and physical review pending',
        }
        print(suffix, 'delivery audit passed', flush=True)
    write(manifest_path, manifest)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison_script = ROOT / 'comparison_audit.py'
    specs = []
    for comparison in plan['comparisons']:
        ident = comparison['comparison_id']
        left, right = [attempts[case] for case in comparison['case_ids']]
        positive = [sys.executable, str(comparison_script), '--comparison', ident,
                    '--left', str(left), '--right', str(right)]
        negative = [sys.executable, str(comparison_script), '--comparison', ident,
                    '--left', str(left), '--right', str(left)]
        positive_log = ROOT / f'comparison-{ident}.log'
        negative_log = ROOT / f'comparison-{ident}-negative.log'
        positive_sha = run(positive, positive_log, 0, '"fixed_conditions_checked": true')
        negative_sha = run(negative, negative_log, 1, 'Exact attempt identity')
        specs.append({'comparison_id': ident, 'case_ids': comparison['case_ids'],
                      'script': comparison_script.name, 'script_sha256': sha(comparison_script),
                      'command': shlex.join(positive),
                      'negative_command': shlex.join(negative),
                      'test_exit_code': 0, 'negative_exit_code': 1,
                      'positive_log': str(positive_log.relative_to(ROOT)),
                      'positive_log_sha256': positive_sha,
                      'negative_log': str(negative_log.relative_to(ROOT)),
                      'negative_log_sha256': negative_sha,
                      'scope': 'Source-bound controlled contrast; no legal finding'})
        print(ident, 'comparison audit passed', flush=True)
    write(ROOT / 'comparison-audit-specs.json', {
        'format': 'worker-comparison-audit-specs', 'assignment_id': ROOT.name,
        'comparisons': specs})


if __name__ == '__main__':
    main()
