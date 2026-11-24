"""Test exact delivery audit positive diagnostics and original-source rejection."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
RETURN = HERE / 'current-public'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'][len(HERE.name) + 2:]
        attempt = SCRATCH / ('c10316-d4-compat-witness1-primary-v8' if suffix == 'witness_1'
                             else 'c10316-d4-compat-' + suffix + '-primary')
        saved = SCRATCH / ('c10316-d4-saved-witness1-primary' if suffix == 'witness_1'
                           else 'c10316-d4-saved-' + suffix + '-primary') / 'v0001/processing.json'
        base = [sys.executable, str(HERE / 'delivery_audit.py'), '--case', entry['case_id'],
                '--candidate', 'primary', '--attempt', str(attempt), '--processing', str(saved)]
        positive_output = RETURN / (suffix + '-delivery-positive.json')
        positive_log = RETURN / (suffix + '-delivery-positive.log')
        positive = [*base, '--output', str(positive_output), '--diagnostic']
        with positive_log.open('w') as stream:
            passed = subprocess.run(positive, cwd=ROOT, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=60)
        if passed.returncode or not json.loads(positive_output.read_text())['diagnostic_only']:
            raise ValueError('Diagnostic delivery audit failed: ' + str(positive_log))
        negative_output = SCRATCH / ('c10316-d4-' + suffix + '-rejected.json')
        negative_log = RETURN / (suffix + '-delivery-negative.log')
        negative = [*base, '--output', str(negative_output)]
        with negative_log.open('w') as stream:
            rejected = subprocess.run(negative, cwd=ROOT, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=60)
        error = 'Original Native source required'
        if rejected.returncode == 0 or error not in negative_log.read_text() or negative_output.exists():
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
            'proof_scope': 'Synthetic software positive and original Native rejection; physical and legal review pending',
        }
        print(suffix, 'delivery diagnostic and negative passed')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print('manifest_sha256', sha(manifest_path))


if __name__ == '__main__':
    main()
