"""Run all exact diagnostic comparison positives and damaged negatives."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = ROOT / 'case-plan.json'
SCRIPT = ROOT / 'comparison_audit.py'
EXPECTED = 'deliberate source difference absent'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    target = ROOT / 'comparisons'
    target.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c229452-comparison-output'))
    for entry in plan['comparisons']:
        name = entry['comparison_id']
        good = [sys.executable, str(SCRIPT), '--comparison', name]
        bad = good + ['--negative']
        positive = subprocess.run(good, cwd=REPO, env=env, capture_output=True, text=True)
        negative = subprocess.run(bad, cwd=REPO, env=env, capture_output=True, text=True)
        if positive.returncode or negative.returncode == 0 or EXPECTED not in negative.stderr:
            raise ValueError(name + ': comparison proof failed: ' + positive.stderr[-500:] + negative.stderr[-500:])
        good_log = target / (name + '-positive.log')
        bad_log = target / (name + '-negative.log')
        good_log.write_text(positive.stdout.rstrip() + '\n')
        bad_log.write_text(negative.stderr.rstrip() + '\n')
        entry['cpu_audit'] = {
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(good), 'exit_code': 0,
            'log': str(good_log.relative_to(ROOT)), 'log_sha256': sha(good_log),
            'negative_command': ' '.join(bad), 'negative_exit_code': negative.returncode,
            'negative_expected_error': EXPECTED,
            'negative_log': str(bad_log.relative_to(ROOT)), 'negative_log_sha256': sha(bad_log),
            'scope': 'source-shaped diagnostic comparison; physical and legal review pending'}
        print(name + ': positive/negative source comparison passed', flush=True)
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    main()
