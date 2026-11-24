"""Run exact selected comparison CPU positives and damaged negatives."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
plan_path = folder / 'case-plan.json'
plan = json.loads(plan_path.read_text())
script = folder / 'comparison_audit.py'
script_sha = hashlib.sha256(script.read_bytes()).hexdigest()
(folder / 'comparisons').mkdir(exist_ok=True)
for entry in plan['comparisons']:
    name = entry['comparison_id']
    positive = [sys.executable, str(script), '--comparison', name]
    negative = positive + ['--negative']
    good = subprocess.run(positive, capture_output=True, text=True)
    bad = subprocess.run(negative, capture_output=True, text=True)
    if good.returncode or bad.returncode == 0 or 'deliberate source difference absent' not in bad.stderr:
        raise ValueError(name + ': comparison proof failed: ' + good.stderr[-300:] + bad.stderr[-300:])
    good_path = folder / 'comparisons' / (name + '-positive.log')
    bad_path = folder / 'comparisons' / (name + '-negative.log')
    good_path.write_text(good.stdout.rstrip() + '\n')
    bad_path.write_text(bad.stderr.rstrip() + '\n')
    entry['cpu_audit'] = {
        'script': 'comparison_audit.py', 'script_sha256': script_sha,
        'command': ' '.join(positive), 'exit_code': 0,
        'log': str(good_path.relative_to(folder)),
        'log_sha256': hashlib.sha256(good_path.read_bytes()).hexdigest(),
        'negative_command': ' '.join(negative), 'negative_exit_code': bad.returncode,
        'negative_expected_error': 'deliberate source difference absent',
        'negative_log': str(bad_path.relative_to(folder)),
        'negative_log_sha256': hashlib.sha256(bad_path.read_bytes()).hexdigest(),
        'scope': 'synthetic diagnostic source comparison; physical and legal review pending',
    }
    print(name + ': positive and negative passed', flush=True)
plan_path.write_text(json.dumps(plan, indent=2) + '\n')
