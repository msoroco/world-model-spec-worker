"""Run public saved diagnostic delivery positive and missing-source negative."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

folder = Path(__file__).resolve().parent.parent
root = folder.parents[1]
manifest_path = folder / 'draft-execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
script = folder / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    edition = 'final9' if suffix == 'false' else 'final8'
    attempt = root / '.runtime-work' / ('c31675-public-' + suffix + '-primary-' + edition)
    saved = root / '.runtime-work' / ('c31675-saved-' + suffix + '-' + edition) / 'v0001/processing.json'
    output = root / '.runtime-work' / ('c31675-delivery-' + suffix + '-positive-' + edition + '-proof1.json')
    proof = folder / 'proofs' / suffix
    proof.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
            '--attempt', str(attempt), '--processing', str(saved), '--output', str(output),
            '--diagnostic']
    positive = subprocess.run(base, cwd=root, capture_output=True, text=True)
    positive_log = proof / 'delivery-positive.log'
    positive_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
    negative_command = base + ['--omit-source', 'bridge-map.json']
    negative = subprocess.run(negative_command, cwd=root, capture_output=True, text=True)
    negative_log = proof / 'delivery-negative.log'
    negative_log.write_text((negative.stdout + negative.stderr).rstrip() + '\n')
    if positive.returncode != 0 or negative.returncode == 0 or \
            'Missing source: bridge-map.json' not in negative_log.read_text():
        raise ValueError('Independent diagnostic audit proof failed for ' + case)
    entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': str(script.relative_to(folder)), 'script_sha256': sha(script),
        'command': ' '.join(base), 'test_exit_code': positive.returncode,
        'test_log': str(positive_log.relative_to(folder)),
        'test_log_sha256': sha(positive_log),
        'negative_command': ' '.join(negative_command),
        'negative_exit_code': negative.returncode,
        'negative_expected_error': 'Missing source: bridge-map.json',
        'negative_log': str(negative_log.relative_to(folder)),
        'negative_log_sha256': sha(negative_log)}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'independent_diagnostic_delivery_audits': len(manifest['cases'])}))
