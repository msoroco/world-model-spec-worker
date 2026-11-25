"""Run and bind the two exact comparison source audits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'audit_comparison.py'
PAIRS = ('witness_comparison', 'exception_1_comparison')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(path, text):
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n' if lines else '')


plan_path = HERE / 'case-plan.json'
plan = json.loads(plan_path.read_text())
for comparison in plan['comparisons']:
    ident = comparison['comparison_id']
    suffix = ident[len(HERE.name) + 2:]
    if suffix not in PAIRS:
        raise ValueError('Unexpected comparison')
    root = HERE / 'proofs' / 'comparisons' / suffix
    root.mkdir(parents=True, exist_ok=True)
    output = root / 'positive.json'
    positive = [sys.executable, str(SCRIPT), '--comparison', ident, '--output', str(output)]
    p = subprocess.run(positive, capture_output=True, text=True)
    positive_log = root / 'positive.log'
    clean(positive_log, p.stdout + p.stderr)
    if p.returncode:
        raise ValueError('Positive comparison failed: ' + p.stderr)
    negative_output = root / 'negative.json'
    left_suffix = 'witness_1' if suffix == 'witness_comparison' else 'exception_1_1'
    negative = [sys.executable, str(SCRIPT), '--comparison', ident,
                '--output', str(negative_output), '--right-override', left_suffix]
    n = subprocess.run(negative, capture_output=True, text=True)
    negative_log = root / 'negative.log'
    clean(negative_log, n.stdout + n.stderr)
    error = 'Selected comparison source differs from planned isolation'
    if n.returncode == 0 or error not in negative_log.read_text():
        raise ValueError('Negative comparison did not reject unchanged device branch')
    comparison['source_audit'] = {
        'script': str(SCRIPT.relative_to(HERE)), 'script_sha256': sha(SCRIPT),
        'command': ' '.join(positive), 'test_exit_code': 0,
        'test_log': str(positive_log.relative_to(HERE)), 'test_log_sha256': sha(positive_log),
        'receipt': str(output.relative_to(HERE)), 'receipt_sha256': sha(output),
        'negative_command': ' '.join(negative), 'negative_exit_code': n.returncode,
        'negative_expected_error': error,
        'negative_log': str(negative_log.relative_to(HERE)),
        'negative_log_sha256': sha(negative_log),
        'diagnostic_fixture': True, 'legal_verdict_claimed': False
    }
    print(suffix, 'positive and negative passed')
plan_path.write_text(json.dumps(plan, indent=2) + '\n')
