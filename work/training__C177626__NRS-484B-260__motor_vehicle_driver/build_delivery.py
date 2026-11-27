"""Bind exact independent original-source delivery audit positive/negative CPU proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c177626-entry'
SCRIPT = ROOT / 'delivery_audit.py'
MANIFEST = ROOT / 'execution-manifest.json'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
    for suffix, entry in zip(('a', 'b'), manifest['cases']):
        proof = ROOT / 'native/proofs' / ('probe_' + suffix)
        positive_log, negative_log = proof / 'delivery-positive.log', proof / 'delivery-negative.log'
        command = [sys.executable, '-B', str(SCRIPT), '--case', entry['case_id'], '--selftest']
        positive = subprocess.run(command, env=env, capture_output=True, text=True)
        if positive.returncode:
            raise RuntimeError(positive.stderr)
        positive_log.write_text(positive.stdout.rstrip() + '\n')
        negative_command = command + ['--negative-fixture']
        negative = subprocess.run(negative_command, env=env, capture_output=True, text=True)
        expected = 'Synthetic fixture cannot establish original Native delivery'
        if negative.returncode == 0 or expected not in negative.stderr:
            raise RuntimeError('Synthetic private-way delivery not rejected as required')
        negative_log.write_text(negative.stderr.rstrip() + '\n')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': str(SCRIPT.relative_to(ROOT)), 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': str(positive_log.relative_to(ROOT)),
            'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': negative.returncode,
            'negative_expected_error': expected,
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': sha(negative_log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2).rstrip() + '\n')
    print('Bound two independent private-way delivery audit contracts')


if __name__ == '__main__':
    main()
