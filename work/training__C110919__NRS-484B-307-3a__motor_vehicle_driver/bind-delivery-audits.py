"""Bind selected source acceptance and comparison audit logs to each case."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110919-3a-owner/delivery'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        output = SCRATCH / witness
        attempt = output / 'attempt'
        processing = output / 'processed/v0001/processing.json'
        if not attempt.is_dir() or not processing.is_file():
            raise ValueError('Selected primary source proof missing')
        positive_log = HERE / f'current-delivery-{witness}-positive.log'
        negative_log = HERE / f'current-delivery-{witness}-negative.log'
        command = ' '.join([str(sys.executable), str(script), '--case', entry['case_id'],
                            '--candidate primary --attempt', str(attempt), '--processing', str(processing),
                            '--output', str(output / 'positive.json'), '--diagnostic'])
        negative_command = ' '.join([str(sys.executable), str(script), '--case', entry['case_id'],
                                     '--candidate primary --attempt', str(output / 'negative-attempt'),
                                     '--processing', str(processing), '--output',
                                     str(output / 'negative.json'), '--diagnostic'])
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': command, 'test_exit_code': 0,
            'test_log': positive_log.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(positive_log),
            'negative_command': negative_command, 'negative_exit_code': 1,
            'negative_expected_error': 'Missing original source: road_geometry.json',
            'negative_log': negative_log.relative_to(HERE).as_posix(),
            'negative_log_sha256': sha(negative_log)}
    manifest['status'] = 'selected_cpu_preparation_original_native_unverified'
    write(path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    build()
