"""Bind positive and stale-pixel negative acceptance protocol tests."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    output = HERE / 'acceptance'
    output.mkdir(exist_ok=True)
    script = HERE / 'acceptance_fixture.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        stem = case.rsplit('__', 1)[-1]
        base = [sys.executable, str(script), '--case', case]
        positive = output / (stem + '-positive.log')
        with positive.open('w') as stream:
            result = subprocess.run(base, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            raise ValueError('Positive delivery fixture failed: ' + case)
        negative = output / (stem + '-negative.log')
        with negative.open('w') as stream:
            failure = subprocess.run(base + ['--negative'], cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT)
        expected = 'Missing original-pixel review: approach'
        if failure.returncode == 0 or expected not in negative.read_text():
            raise ValueError('Stale pixel review fixture was accepted: ' + case)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['held-out'], 'checks': CHECKS,
            'command': ' '.join(base), 'test_exit_code': 0,
            'test_log': str(positive.relative_to(HERE)),
            'test_log_sha256': digest(positive),
            'negative_command': ' '.join(base + ['--negative']),
            'negative_exit_code': failure.returncode,
            'negative_expected_error': expected,
            'negative_log': str(negative.relative_to(HERE)),
            'negative_log_sha256': digest(negative),
            'script': script.name, 'script_sha256': digest(script),
            'fixture_only': True}
        print(stem, 'delivery acceptance protocol passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
