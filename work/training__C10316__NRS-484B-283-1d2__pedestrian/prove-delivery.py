"""Bind selected cases to diagnostic positive and original-source rejection."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c10316-1d2-public-v1'
RETURN = HERE / 'current-public'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = SCRATCH / (suffix + '-primary')
        attempt = folder / 'compat'
        processing = folder / 'saved/v0001/processing.json'
        base = [sys.executable, str(HERE / 'delivery_audit.py'),
                '--case', entry['case_id'], '--candidate', 'primary',
                '--attempt', str(attempt), '--processing', str(processing)]
        positive_out = RETURN / (suffix + '-delivery-positive.json')
        positive_log = RETURN / (suffix + '-delivery-positive.log')
        positive = [*base, '--output', str(positive_out), '--diagnostic']
        with positive_log.open('w') as log:
            run = subprocess.run(positive, cwd=ROOT, stdout=log,
                                 stderr=subprocess.STDOUT, timeout=60)
        if run.returncode or not json.loads(positive_out.read_text())['diagnostic_only']:
            raise ValueError('Diagnostic delivery path failed: ' + str(positive_log))
        negative_out = SCRATCH / (suffix + '-delivery-rejected.json')
        negative_log = RETURN / (suffix + '-delivery-negative.log')
        negative = [*base, '--output', str(negative_out)]
        with negative_log.open('w') as log:
            rejected = subprocess.run(negative, cwd=ROOT, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=60)
        error = 'Original Native source required'
        if rejected.returncode == 0 or error not in negative_log.read_text() or negative_out.exists():
            raise ValueError('Synthetic original-source negative did not reject')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': ' '.join(positive), 'test_exit_code': 0,
            'test_log': positive_log.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative),
            'negative_exit_code': rejected.returncode,
            'negative_expected_error': error,
            'negative_log': negative_log.relative_to(HERE).as_posix(),
            'negative_log_sha256': sha(negative_log),
            'proof_scope': 'Synthetic software diagnostic positive and original Native rejection; physical and legal review pending'}
        print(suffix, 'positive and negative passed')
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print('manifest_sha256', sha(path))


if __name__ == '__main__':
    main()
