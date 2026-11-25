"""Prove selected delivery source joins and original-source rejection per case."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'delivery-audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        number = case.rsplit('_', 1)[-1]
        base = f'delivery-probe-{number}'
        positive_log = HERE / f'{base}-positive.log'
        negative_log = HERE / f'{base}-negative.log'
        command = [sys.executable, str(SCRIPT), '--case', case, '--diagnostic']
        negative_command = command[:-1]
        positive = subprocess.run(command, text=True, capture_output=True, check=False)
        negative = subprocess.run(negative_command, text=True, capture_output=True, check=False)
        positive_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
        negative_log.write_text((negative.stdout + negative.stderr).rstrip() + '\n')
        expected_error = 'Original Native two-actor body passage and four camera pixels required for delivery acceptance'
        if positive.returncode or not json.loads(positive.stdout)['diagnostic_only']:
            raise ValueError(f'Positive selected delivery audit failed: {positive.stderr}')
        if negative.returncode == 0 or expected_error not in negative_log.read_text():
            raise ValueError('Original-source negative audit did not reject')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery-audit.py', 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': negative.returncode,
            'negative_expected_error': expected_error,
            'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log)}
        print(case, 'selected delivery audit passed; original-only negative rejected')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
