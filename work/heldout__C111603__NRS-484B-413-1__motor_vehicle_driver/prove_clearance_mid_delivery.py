"""Record positive and stale-source rejection of the exact intermediate attempt."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'clearance-mid-manifest.json'
manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
script = ROOT / 'clearance_mid_audit.py'
base = [PY, str(script.relative_to(REPO)), '--case', entry['case_id'],
        '--attempt', '.runtime-work/c111603-clearance-mid-primary-compat-f',
        '--baseline', '.runtime-work/c111603-vehicle-indicator-compat-d',
        '--output', str((ROOT / 'clearance-mid-audit.json').relative_to(REPO))]

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def run(command, log):
    with log.open('w') as stream:
        return subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT).returncode

positive = ROOT / 'clearance-mid-audit.log'
negative = ROOT / 'clearance-mid-stale-audit.log'
assert run(base, positive) == 0
assert run(base + ['--negative'], negative) != 0
assert 'Stale or missing original clearance source' in negative.read_text()
entry['delivery_acceptance'] = {
    'case_id': entry['case_id'], 'sets': ['held-out'],
    'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
    'script': script.name, 'script_sha256': sha(script),
    'command': ' '.join(base), 'test_exit_code': 0, 'test_log': positive.name,
    'test_log_sha256': sha(positive), 'negative_command': ' '.join(base + ['--negative']),
    'negative_exit_code': 1, 'negative_expected_error': 'Stale or missing original clearance source',
    'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Exact intermediate delivery audit and stale-source rejection passed')
