"""Retain independent delivery/comparison positive and missing-source negatives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from comparison_audit import PAIRS

HERE = Path(__file__).resolve().parent
AID = HERE.name
PYTHON = sys.executable


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(name, argv, expected):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([PYTHON, *argv], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=120)
    path = HERE / (name + '.log')
    path.write_text(result.stdout.rstrip() + '\n')
    if (result.returncode == 0) != expected:
        raise ValueError('Independent audit selftest exit differs: ' + name)
    return {'command': ' '.join([PYTHON, *argv]), 'exit_code': result.returncode,
            'log': path.name, 'log_sha256': sha(path)}


def main():
    delivery = {}
    for slug in ('probe_1', 'probe_2', 'probe_3', 'probe_4', 'probe_5'):
        case = AID + '__' + slug
        good = run('delivery-' + slug + '-positive',
                   ['delivery_audit.py', '--case', case, '--self-test'], True)
        bad = run('delivery-' + slug + '-negative',
                  ['delivery_audit.py', '--case', case, '--self-test', '--negative'], False)
        if 'Exact original Native result missing' not in (HERE / bad['log']).read_text():
            raise ValueError('Native-source negative failed to reject: ' + slug)
        delivery[slug] = {'positive': good, 'negative': bad,
                          'negative_expected_error': 'Exact original Native result missing'}
    comparison = {}
    for name in PAIRS:
        label = name.rsplit('__', 1)[-1]
        good = run('comparison-' + label + '-positive',
                   ['comparison_audit.py', '--comparison', name, '--self-test'], True)
        bad = run('comparison-' + label + '-negative',
                  ['comparison_audit.py', '--comparison', name, '--self-test', '--negative'], False)
        if 'Fixed original actor, road motion or source clock changed' not in (HERE / bad['log']).read_text():
            raise ValueError('Comparison negative failed to reject: ' + label)
        comparison[name] = {'positive': good, 'negative': bad}
    path = HERE / 'independent-audit-proof.json'
    path.write_text(json.dumps({'format': 'worker-freight-zone-independent-audit-cpu',
                                'diagnostic_only': True,
                                'delivery': delivery, 'comparisons': comparison},
                               indent=2, ensure_ascii=False) + '\n')
    return {'delivery_cases': len(delivery), 'comparisons': len(comparison),
            'proof_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
