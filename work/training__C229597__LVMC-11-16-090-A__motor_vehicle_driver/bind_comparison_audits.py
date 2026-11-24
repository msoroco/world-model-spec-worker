"""Bind CPU positive and missing-case comparison audits to exact plans."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
PLAN = PACKAGE / 'case-plan.json'
SCRIPT = PACKAGE / 'audit_comparisons.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    env = dict(os.environ, TMPDIR=str(ROOT / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    for comparison in plan['comparisons']:
        cid = comparison['comparison_id']
        suffix = cid.rsplit('__', 1)[-1]
        directory = PACKAGE / 'comparison-proofs' / suffix
        directory.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(SCRIPT), '--comparison', cid]
        positive = directory / 'positive.log'
        negative = directory / 'negative.log'
        with positive.open('w') as stream:
            good = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        with negative.open('w') as stream:
            bad = subprocess.run(command + ['--remove-case'], cwd=ROOT, env=env,
                                 stdout=stream, stderr=subprocess.STDOUT)
        expected = 'Comparison missing exact planned case'
        if good.returncode != 0 or bad.returncode == 0 or expected not in negative.read_text():
            raise ValueError('Comparison positive/negative failed: ' + cid)
        result = json.loads(positive.read_text())
        if result.get('passed') is not True or result.get('legal_outcome_claimed') is not False:
            raise ValueError('Comparison result invalid: ' + cid)
        comparison['cpu_audit'] = {
            'command': ' '.join(command), 'script': str(SCRIPT.relative_to(PACKAGE)),
            'script_sha256': sha(SCRIPT), 'positive_log': str(positive.relative_to(PACKAGE)),
            'positive_log_sha256': sha(positive), 'positive_exit_code': good.returncode,
            'negative_command': ' '.join(command + ['--remove-case']),
            'negative_log': str(negative.relative_to(PACKAGE)),
            'negative_log_sha256': sha(negative), 'negative_exit_code': bad.returncode,
            'negative_expected_error': expected, 'native_executed': False,
            'legal_outcome_claimed': False}
        print(cid, 'positive and negative passed', flush=True)
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    main()
