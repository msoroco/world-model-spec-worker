"""Exercise independent delivery source audit with three positive/negative pairs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111334-resume'
SUFFIXES = ('probe_1', 'probe_2', 'permission_before_entry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def clean(text):
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'


def prove():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set output root under .runtime-work')
    outcomes = {}
    for suffix in SUFFIXES:
        case_id = PACKAGE.name + '__' + suffix
        attempt = SCRATCH / ('compat-' + suffix + '-v8')
        directory = PACKAGE / 'native-selected' / suffix
        positive_path = directory / 'delivery-positive.json'
        positive_command = [sys.executable, '-B', str(HERE / 'delivery_acceptance.py'),
                            '--attempt', str(attempt), '--case', case_id,
                            '--output', str(positive_path), '--diagnostic']
        positive = subprocess.run(positive_command, text=True, capture_output=True,
                                  cwd=ROOT, env=os.environ.copy(), timeout=120)
        (directory / 'delivery-positive.log').write_text(clean(positive.stdout + positive.stderr))
        if positive.returncode != 0:
            raise RuntimeError('Positive delivery audit failed: ' + suffix)
        receipt = json.loads(positive_path.read_text())
        if receipt['diagnostic_fixture'] is not True or receipt['physical_acceptance'] is not False:
            raise AssertionError('Diagnostic delivery proof claimed physical acceptance')
        negative_command = [sys.executable, '-B', str(HERE / 'delivery_acceptance.py'),
                            '--attempt', str(attempt), '--case', case_id,
                            '--output', str(output_root / ('negative-' + suffix + '.json'))]
        negative = subprocess.run(negative_command, text=True, capture_output=True,
                                  cwd=ROOT, env=os.environ.copy(), timeout=120)
        (directory / 'delivery-negative.log').write_text(clean(negative.stdout + negative.stderr))
        if negative.returncode == 0 or 'Original Native delivery source required' not in negative.stderr:
            raise AssertionError('Synthetic source was accepted for original delivery')
        outcomes[suffix] = {
            'case_id': case_id, 'script': 'native/delivery_acceptance.py',
            'script_sha256': sha(HERE / 'delivery_acceptance.py'),
            'checks': receipt['checks'],
            'positive_exit_code': 0,
            'positive_receipt': 'native-selected/' + suffix + '/delivery-positive.json',
            'positive_sha256': sha(positive_path),
            'positive_log': 'native-selected/' + suffix + '/delivery-positive.log',
            'positive_log_sha256': sha(directory / 'delivery-positive.log'),
            'negative_exit_code': negative.returncode,
            'negative_expected_error': 'Original Native delivery source required',
            'negative_log': 'native-selected/' + suffix + '/delivery-negative.log',
            'negative_log_sha256': sha(directory / 'delivery-negative.log'),
            'positive_command': ' '.join(str(x) for x in positive_command),
            'negative_command': ' '.join(str(x) for x in negative_command),
        }
    proof = {'format': 'c111334-delivery-cpu-proof-v1',
             'assignment_id': PACKAGE.name, 'cases': outcomes,
             'synthetic_diagnostic_only': True,
             'physical_acceptance_claimed': False}
    target = HERE / 'delivery-cpu-proof.json'
    save(target, proof)
    return {'cases': len(outcomes), 'proof_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
