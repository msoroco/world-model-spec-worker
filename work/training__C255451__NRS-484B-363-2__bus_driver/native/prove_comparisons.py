"""Exercise positive and missing-member negative for five exact comparisons."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
AUDITOR = ROOT / 'audit_comparisons.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    receipts = []
    for comparison in plan['comparisons']:
        ident = comparison['comparison_id']
        suffix = ident.rsplit('__', 1)[-1]
        base = [sys.executable, '-B', str(AUDITOR), '--comparison', ident]
        env = {**os.environ, 'TMPDIR': str(REPO / '.runtime-work')}
        positive = subprocess.run(base, cwd=REPO, text=True, capture_output=True, env=env)
        positive_log = ROOT / ('comparison-' + suffix + '-positive.log')
        positive_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
        if positive.returncode:
            raise ValueError('Comparison failed: ' + suffix + ' ' + positive_log.read_text())
        negative = subprocess.run(base + ['--negative-drop-last'], cwd=REPO,
                                  text=True, capture_output=True, env=env)
        negative_log = ROOT / ('comparison-' + suffix + '-negative.log')
        negative_log.write_text((negative.stdout + negative.stderr).rstrip() + '\n')
        if negative.returncode == 0 or 'Missing comparison source receipt' not in negative_log.read_text():
            raise ValueError('Comparison negative failed: ' + suffix)
        receipt = json.loads(positive.stdout)
        receipt.update({'auditor': str(AUDITOR.relative_to(ROOT)), 'auditor_sha256': sha(AUDITOR),
                        'command': ' '.join(base), 'negative_command': ' '.join(base + ['--negative-drop-last']),
                        'positive_log': str(positive_log.relative_to(ROOT)), 'positive_log_sha256': sha(positive_log),
                        'negative_log': str(negative_log.relative_to(ROOT)), 'negative_log_sha256': sha(negative_log)})
        receipts.append(receipt)
        comparison['status'] = 'source_bound_cpu_comparison_passed'
        comparison['audit_gap'] = 'Original Native evidence and official source review remain local delivery checks'
        print('comparison ' + suffix, flush=True)
    (ROOT / 'comparison-audit.json').write_text(json.dumps({'comparisons': receipts}, indent=2) + '\n')
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    run()
