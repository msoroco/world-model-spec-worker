"""Bind CPU positive and synthetic-as-physical rejection for each exact case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
SCRIPT = FOLDER / 'delivery_acceptance.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work' / 'c262666-test' / 'output'),
               TMPDIR=str(REPO / '.runtime-work' / 'c262666-test'), PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        source = REPO / '.runtime-work' / 'c262666-test' / ('compat-r5' if suffix == 'probe_03' else f'compat-{suffix}-r1')
        positive = FOLDER / f'delivery-{suffix}-positive.json'
        negative = FOLDER / f'delivery-{suffix}-negative.json'
        command = [sys.executable, str(SCRIPT), '--attempt', str(source), '--case', entry['case_id'],
                   '--diagnostic', '--output', str(positive)]
        test = subprocess.run(command, text=True, capture_output=True, env=env)
        positive_log = FOLDER / f'delivery-{suffix}-positive.log'
        positive_log.write_text((test.stdout + test.stderr).rstrip() + '\n')
        if test.returncode:
            raise ValueError(f'{suffix} positive audit failed: {test.stderr[-500:]}')
        negative_command = [sys.executable, str(SCRIPT), '--attempt', str(source), '--case', entry['case_id'],
                            '--output', str(negative)]
        rejected = subprocess.run(negative_command, text=True, capture_output=True, env=env)
        negative_log = FOLDER / f'delivery-{suffix}-negative.log'
        negative_log.write_text((rejected.stdout + rejected.stderr).rstrip() + '\n')
        expected = 'Missing delivery source: capture-seal.json'
        if rejected.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError(f'{suffix} synthetic-as-physical audit was not rejected')
        entry['delivery_acceptance'] = {'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command), 'negative_exit_code': rejected.returncode,
            'negative_expected_error': expected, 'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log),
            'proof_scope': 'Synthetic source join and synthetic-as-physical rejection only'}
        print(suffix, 'audit pass/reject', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
