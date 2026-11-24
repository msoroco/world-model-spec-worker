"""Bind exact positive and missing-source CPU delivery audits for eight cases."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
SCRIPT = PACKAGE / 'audit_delivery_cpu.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, TMPDIR=str(ROOT / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        if suffix.startswith('judgment-'):
            log_dir = PACKAGE / 'sweep-cases' / case / 'delivery'
        else:
            log_dir = PACKAGE
        log_dir.mkdir(parents=True, exist_ok=True)
        positive = log_dir / (('positive.log' if suffix.startswith('judgment-') else 'delivery-' + suffix + '-positive.log'))
        negative = log_dir / (('negative.log' if suffix.startswith('judgment-') else 'delivery-' + suffix + '-negative.log'))
        command = [sys.executable, str(SCRIPT), '--case', case]
        with positive.open('w') as stream:
            good = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        with negative.open('w') as stream:
            bad = subprocess.run(command + ['--remove-source'], cwd=ROOT, env=env,
                                 stdout=stream, stderr=subprocess.STDOUT)
        expected = 'Missing required source: trace.jsonl'
        if good.returncode != 0 or bad.returncode == 0 or expected not in negative.read_text():
            raise ValueError(f'Delivery audit did not pass positive/negative: {case}')
        result = json.loads(positive.read_text())
        if result.get('passed') is not True or result.get('accepted') is not False:
            raise ValueError('Delivery audit claimed acceptance: ' + case)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': str(SCRIPT.relative_to(PACKAGE)), 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': good.returncode,
            'test_log': str(positive.relative_to(PACKAGE)), 'test_log_sha256': sha(positive),
            'negative_command': ' '.join(command + ['--remove-source']),
            'negative_exit_code': bad.returncode, 'negative_expected_error': expected,
            'negative_log': str(negative.relative_to(PACKAGE)), 'negative_log_sha256': sha(negative),
            'cpu_scope': 'synthetic source audit; original pixels and physical completion unverified'}
        print(case, 'delivery positive and negative passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
