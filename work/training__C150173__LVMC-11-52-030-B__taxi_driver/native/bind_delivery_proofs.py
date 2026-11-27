"""Retain exact synthetic positive and changed-pixel negative audit tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
SCRIPT = PACKAGE / 'native/delivery_audit.py'
TEST = PACKAGE / 'native/test_delivery.py'
EXPECTED = 'Original actual-pixel review is not video-bound: sign-review.json'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case, negative, log_path, test, expected):
    command = [sys.executable, '-B', str(test), '--case', case]
    if negative:
        command.append('--negative-pixels')
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=120)
    log_path.write_text(completed.stdout.rstrip('\n') + '\n')
    if ((not negative and completed.returncode != 0) or
            (negative and (completed.returncode == 0 or expected not in completed.stdout))):
        raise ValueError('Exact taxi independent delivery test differs: ' + case)
    return completed.returncode


def main():
    index = []
    for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d',
                   'freight_load', 'freight_unload', 'freight_wait'):
        case = PACKAGE.name + '__' + suffix
        freight = suffix.startswith('freight_')
        script = PACKAGE / 'native' / ('freight_delivery_audit.py' if freight else 'delivery_audit.py')
        test = PACKAGE / 'native' / ('test_freight_delivery.py' if freight else 'test_delivery.py')
        expected = ('Original freight actual-pixel review is not video-bound: sign-review.json'
                    if freight else EXPECTED)
        destination = PACKAGE / 'native-selected' / suffix
        positive = destination / 'delivery-positive.log'
        negative = destination / 'delivery-negative-pixels.log'
        good = run(case, False, positive, test, expected)
        bad = run(case, True, negative, test, expected)
        receipt = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': str(script.relative_to(PACKAGE)), 'script_sha256': sha(script),
            'command': '.venv-cpu/bin/python -B work/' + PACKAGE.name +
                       '/' + str(test.relative_to(PACKAGE)) + ' --case ' + case,
            'test_exit_code': good,
            'test_log': str(positive.relative_to(PACKAGE)),
            'test_log_sha256': sha(positive),
            'negative_command': '.venv-cpu/bin/python -B work/' + PACKAGE.name +
                                '/' + str(test.relative_to(PACKAGE)) + ' --case ' + case +
                                ' --negative-pixels',
            'negative_exit_code': bad,
            'negative_expected_error': expected,
            'negative_log': str(negative.relative_to(PACKAGE)),
            'negative_log_sha256': sha(negative),
            'diagnostic_scope': 'Synthetic structural audit test; original pixels and physical acceptance unobserved'}
        index.append(receipt)
    path = PACKAGE / 'native-selected/delivery-proof-index.json'
    path.write_text(json.dumps({'format': 'c150173-independent-delivery-proofs-v1',
                                'cases': index}, indent=2) + '\n')
    print(json.dumps({'cases': len(index), 'sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
