"""Bind positive and missing-case CPU comparison receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    rows = [line.rstrip() for line in (result.stdout + result.stderr).splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    log.write_text('\n'.join(rows) + '\n' if rows else '')
    return result.returncode


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    script = HERE / 'comparison_audit.py'
    for spec in plan['comparisons']:
        name = spec['comparison_id']
        command = [sys.executable, str(script), '--comparison', name]
        for case in spec['case_ids']:
            suffix = case.rsplit('__', 1)[1]
            processing = ROOT / '.runtime-work' / f'c110875-saved-{suffix}-primary-1/v0001/processing.json'
            command.extend(['--processing', case + '=' + str(processing)])
        command.extend(['--output', str(ROOT / '.runtime-work/c110875-taxi-comparison-positive-1.json')])
        positive = HERE / 'proofs/comparison-positive.log'
        negative = HERE / 'proofs/comparison-negative.log'
        passed = run(command, positive)
        rejected_command = command + ['--omit-case', spec['case_ids'][-1]]
        rejected = run(rejected_command, negative)
        if passed != 0 or rejected == 0 or 'Missing comparison case' not in negative.read_text():
            raise ValueError('Comparison CPU positive or negative failed')
        spec['audit'] = {'script': 'comparison_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(command), 'test_log': 'proofs/comparison-positive.log',
            'test_log_sha256': sha(positive), 'test_exit_code': 0,
            'negative_command': ' '.join(rejected_command),
            'negative_log': 'proofs/comparison-negative.log', 'negative_log_sha256': sha(negative),
            'negative_exit_code': rejected}
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'comparisons': len(plan['comparisons'])}))


if __name__ == '__main__':
    main()
