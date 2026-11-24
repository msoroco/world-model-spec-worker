"""Bind positive and negative CPU mocks of the independent delivery audit."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-draft-execution-manifest.json'
SCRIPT = HERE / 'native/prove_delivery_contract.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    lines = [line.rstrip() for line in value.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'


manifest = json.loads(MANIFEST.read_text())
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    base = [sys.executable, str(SCRIPT), '--case', case]
    outputs = []
    for negative in (False, True):
        command = base + (['--negative'] if negative else [])
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert run.returncode == (2 if negative else 0), run.stdout
        log = HERE / f'selected-{suffix}-delivery-{("negative" if negative else "positive")}.log'
        log.write_text(clean(run.stdout))
        outputs.append((command, run.returncode, log))
    positive, negative = outputs
    assert 'EXPECTED CPU MOCK REJECTION: Original delivery sources changed' in negative[2].read_text()
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['full-train'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': str(SCRIPT.relative_to(HERE)), 'script_sha256': sha(SCRIPT),
        'command': ' '.join(positive[0]), 'test_exit_code': 0,
        'test_log': positive[2].name, 'test_log_sha256': sha(positive[2]),
        'negative_command': ' '.join(negative[0]), 'negative_exit_code': 2,
        'negative_log': negative[2].name, 'negative_log_sha256': sha(negative[2]),
        'negative_expected_error': 'EXPECTED CPU MOCK REJECTION: Original delivery sources changed',
        'proof_scope': 'mocked_original_delivery_contract_only',
        'original_native_observed': False, 'delivery_acceptance_claimed': False}
MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(sha(MANIFEST))
