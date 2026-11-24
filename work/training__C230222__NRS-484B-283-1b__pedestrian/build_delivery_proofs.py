"""Bind exact curb cases to diagnostic and original-source rejection proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(ROOT / '.runtime-work'))
    result = subprocess.run(command, cwd=ROOT, capture_output=True,
                            text=True, env=env)
    log.write_text((result.stdout + result.stderr).rstrip('\n') + '\n')
    return result.returncode


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        number = suffix.rsplit('_', 1)[-1]
        attempt = ROOT / '.runtime-work' / f'c230222-map-r3-probe_{number}-primary-compat'
        processing = ROOT / '.runtime-work' / f'c230222-map-r3-probe_{number}-primary-saved' / 'v0001/processing.json'
        folder = HERE / 'delivery-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        base = [sys.executable, str(SCRIPT), '--case', case,
                '--candidate', 'primary', '--attempt', str(attempt),
                '--processing', str(processing)]
        positive = base + ['--output', str(ROOT / '.runtime-work' / f'c230222-map-r3-{suffix}-diagnostic-final.json'), '--diagnostic']
        negative = base + ['--output', str(ROOT / '.runtime-work' / f'c230222-map-r3-{suffix}-rejected-final.json')]
        positive_log, negative_log = folder / 'positive.log', folder / 'negative.log'
        positive_code = run(positive, positive_log)
        negative_code = run(negative, negative_log)
        expected = 'Original Native source required'
        if positive_code != 0 or negative_code == 0 or expected not in negative_log.read_text():
            raise ValueError('Delivery audit CPU proof failed: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
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
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_audit_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
