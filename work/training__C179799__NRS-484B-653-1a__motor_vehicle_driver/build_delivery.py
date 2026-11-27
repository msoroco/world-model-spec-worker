"""Bind exact independent original-delivery CPU positive/negative selftests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO/'.runtime-work/c179799/delivery-selftests'
SCRIPT = HERE/'delivery_audit.py'
EXPECTED = 'Synthetic fixture cannot establish original Native delivery'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE/'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof_root = HERE/'delivery-proofs'/suffix
        proof_root.mkdir(parents=True, exist_ok=True)
        commands = []
        for negative in (False, True):
            command = [sys.executable, '-B', str(SCRIPT), '--case', entry['case_id'], '--selftest']
            if negative:
                command.append('--negative-fixture')
            process = subprocess.run(command, capture_output=True, text=True,
                                     env=dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                                              TMPDIR=str(REPO/'.runtime-work')))
            log = proof_root/('negative.log' if negative else 'positive.log')
            log.write_text((process.stdout+process.stderr).rstrip()+'\n')
            if (negative and (process.returncode == 0 or EXPECTED not in log.read_text())) or (
                    not negative and process.returncode != 0):
                raise RuntimeError('Delivery selftest failed: '+str(command)+': '+log.read_text())
            commands.append((command, process.returncode, log))
        positive, negative = commands
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(SCRIPT),
            'command': ' '.join(positive[0]), 'test_exit_code': positive[1],
            'test_log': str(positive[2].relative_to(HERE)),
            'test_log_sha256': sha(positive[2]),
            'negative_command': ' '.join(negative[0]),
            'negative_exit_code': negative[1],
            'negative_expected_error': EXPECTED,
            'negative_log': str(negative[2].relative_to(HERE)),
            'negative_log_sha256': sha(negative[2])}
    write(manifest_path, manifest)
    print('PASS: two independent exact delivery acceptance selftests bound')


if __name__ == '__main__':
    main()
