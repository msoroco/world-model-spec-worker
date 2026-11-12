"""Bind exact positive and stale-source rejection audits for timing points."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
SCRIPT = HERE / 'indicator_activation_audit.py'

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def run(command, log):
    with log.open('w') as stream:
        return subprocess.run(command, cwd=REPO, stdout=stream,
                              stderr=subprocess.STDOUT).returncode

for activation in (2, 4, 6):
    prefix = f'indicator-activation-{activation}f'
    path = HERE / f'{prefix}-manifest.json'
    manifest = json.loads(path.read_text())
    entry = manifest['cases'][0]
    base = [PY, str(SCRIPT.relative_to(REPO)), '--activation', str(activation),
            '--case', entry['case_id'],
            '--attempt', f'.runtime-work/c111603-{prefix}-primary-compat-a',
            '--baseline', '.runtime-work/c111603-no-indicator-primary-compat-c',
            '--output', str((HERE / f'{prefix}-audit.json').relative_to(REPO))]
    positive = HERE / f'{prefix}-audit.log'
    negative = HERE / f'{prefix}-stale-audit.log'
    assert run(base, positive) == 0
    assert run(base + ['--negative'], negative) != 0
    assert 'Stale or missing original indicator timing source' in negative.read_text()
    entry['delivery_acceptance'] = {
        'case_id': entry['case_id'], 'sets': ['held-out'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
        'command': ' '.join(base), 'test_exit_code': 0,
        'test_log': positive.name, 'test_log_sha256': sha(positive),
        'negative_command': ' '.join(base + ['--negative']),
        'negative_exit_code': 1,
        'negative_expected_error': 'Stale or missing original indicator timing source',
        'negative_log': negative.name,
        'negative_log_sha256': sha(negative)}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(activation, 'delivery and stale-source rejection passed', flush=True)
