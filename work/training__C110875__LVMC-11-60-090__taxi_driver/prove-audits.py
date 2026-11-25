"""Exercise independent taxi delivery source audits and rejection paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(tokens, log):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True)
    rows = [line.rstrip() for line in (result.stdout + result.stderr).splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    log.write_text('\n'.join(rows) + '\n' if rows else '')
    return result.returncode


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        proof = HERE / 'proofs' / suffix
        attempt = ROOT / '.runtime-work' / f'c110875-saved-attempt-{suffix}-primary-1'
        processing = ROOT / '.runtime-work' / f'c110875-saved-{suffix}-primary-1/v0001/processing.json'
        command = [sys.executable, str(script), '--case', case,
            '--attempt', str(attempt), '--processing', str(processing),
            '--output', str(ROOT / '.runtime-work' / f'c110875-delivery-audit-{suffix}-positive-2.json'),
            '--diagnostic']
        positive = proof / 'delivery-positive.log'
        negative = proof / 'delivery-negative.log'
        passed = run(command, positive)
        rejected_command = command[:-1] + ['--diagnostic', '--omit-source', 'route-survey.json']
        rejected = run(rejected_command, negative)
        if passed != 0 or rejected == 0 or 'Missing source: route-survey.json' not in negative.read_text():
            raise ValueError('Delivery audit positive or negative proof failed: ' + case)
        entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion', 'stand_sign_street_authority'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(command), 'test_exit_code': passed,
            'test_log': str(positive.relative_to(HERE)), 'test_log_sha256': sha(positive),
            'negative_command': ' '.join(rejected_command),
            'negative_exit_code': rejected, 'negative_expected_error': 'Missing source: route-survey.json',
            'negative_log': str(negative.relative_to(HERE)), 'negative_log_sha256': sha(negative)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_audits': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
