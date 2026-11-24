"""Bind positive diagnostic and missing-source rejection to the selected audit."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110454-450-fallbacks'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def command(case, attempt, processing, output):
    return [sys.executable, str(HERE / 'delivery_audit.py'), '--case', case,
            '--candidate', 'primary', '--attempt', str(attempt),
            '--processing', str(processing), '--output', str(output), '--diagnostic']


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = SCRATCH / f'compat3-{suffix}-primary'
        processed = SCRATCH / f'saved3-{suffix}-primary/v0001/processing.json'
        scratch = Path(tempfile.mkdtemp(prefix=f'c110454-{suffix}-delivery-', dir=ROOT / '.runtime-work'))
        positive_cmd = command(entry['case_id'], source, processed, scratch / 'positive.json')
        positive = subprocess.run(positive_cmd, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=1800)
        if positive.returncode != 0:
            raise ValueError('Positive diagnostic failed: ' + positive.stdout)
        positive_receipt = json.loads((scratch / 'positive.json').read_text())
        if positive_receipt.get('accepted') or positive_receipt.get('actual_pixels_verified'):
            raise ValueError('Synthetic diagnostic claimed physical acceptance')
        negative_source = scratch / 'missing-road-attempt'
        shutil.copytree(source, negative_source)
        (negative_source / 'road_geometry.json').unlink()
        negative_cmd = command(entry['case_id'], negative_source, processed, scratch / 'negative.json')
        negative = subprocess.run(negative_cmd, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=1800)
        expected = 'Missing original source: road_geometry.json'
        if negative.returncode == 0 or expected not in negative.stdout:
            raise ValueError('Missing source was not rejected: ' + negative.stdout)
        directory = HERE / 'delivery-proofs' / suffix
        positive_log = directory / 'positive.log'
        negative_log = directory / 'negative.log'
        directory.mkdir(parents=True, exist_ok=True)
        positive_log.write_text(positive.stdout.rstrip() + '\n')
        negative_log.write_text(negative.stdout.rstrip() + '\n')
        write(directory / 'diagnostic.json', positive_receipt)
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': ' '.join(positive_cmd), 'test_exit_code': 0,
            'test_log': positive_log.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_cmd),
            'negative_exit_code': negative.returncode,
            'negative_expected_error': expected,
            'negative_log': negative_log.relative_to(HERE).as_posix(),
            'negative_log_sha256': sha(negative_log)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
