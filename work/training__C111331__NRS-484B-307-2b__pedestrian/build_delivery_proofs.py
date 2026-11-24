"""Run exact-case diagnostic positives and original-source rejection proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111331-current'
SCRIPT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'))
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    log.write_text((result.stdout + result.stderr).rstrip('\n') + '\n')
    return result.returncode


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        attempt = SCRATCH / f'{suffix}-compat-final'
        processing = SCRATCH / f'{suffix}-saved-final/v0001/processing.json'
        folder = HERE / 'delivery-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        base = [sys.executable, str(SCRIPT), '--case', case_id,
                '--candidate', 'primary', '--attempt', str(attempt),
                '--processing', str(processing)]
        positive = base + ['--output', str(SCRATCH / f'{suffix}-delivery-diagnostic-v3.json'),
                           '--diagnostic']
        negative = base + ['--output', str(SCRATCH / f'{suffix}-delivery-rejected.json')]
        positive_log, negative_log = folder / 'positive.log', folder / 'negative.log'
        positive_code = run(positive, positive_log)
        negative_code = run(negative, negative_log)
        expected = 'Original Native source required'
        if positive_code != 0 or negative_code == 0 or expected not in negative_log.read_text():
            raise ValueError('Delivery audit CPU proof failed: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(SCRIPT),
            'command': ' '.join(positive), 'test_exit_code': positive_code,
            'test_log': str(positive_log.relative_to(HERE)),
            'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative),
            'negative_exit_code': negative_code,
            'negative_expected_error': expected,
            'negative_log': str(negative_log.relative_to(HERE)),
            'negative_log_sha256': sha(negative_log),
            'proof_scope': 'Synthetic software positive and original Native rejection; no physical acceptance'}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_audit_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
