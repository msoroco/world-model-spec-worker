"""Run independent saved-source fixture audit for each exact speed case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
SCRIPT = FOLDER / 'delivery_acceptance.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_log(path, completed):
    path.write_text((completed.stdout + completed.stderr).rstrip() + '\n')


def main():
    path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work' / 'c230259-audit-runtime'),
               TMPDIR=str(REPO / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        attempt = REPO / '.runtime-work' / f'c230259-saved-attempt-{suffix}-v2'
        positive = FOLDER / 'native' / 'proofs' / suffix / 'delivery-positive.json'
        negative = REPO / '.runtime-work' / f'c230259-delivery-{suffix}-negative.json'
        prefix = [sys.executable, '-B', str(SCRIPT), '--attempt', str(attempt), '--case', case]
        command = prefix + ['--diagnostic', '--output', str(positive)]
        passed = subprocess.run(command, text=True, capture_output=True, env=env)
        positive_log = FOLDER / 'native' / 'proofs' / suffix / 'delivery-positive.log'
        write_log(positive_log, passed)
        if passed.returncode:
            raise ValueError(f'{suffix} positive delivery audit failed: {passed.stderr[-500:]}')
        negative_command = prefix + ['--output', str(negative)]
        rejected = subprocess.run(negative_command, text=True, capture_output=True, env=env)
        negative_log = FOLDER / 'native' / 'proofs' / suffix / 'delivery-negative.log'
        write_log(negative_log, rejected)
        expected = 'Missing delivery source: capture-seal.json'
        if rejected.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError(f'{suffix} synthetic-as-physical audit was not rejected')
        rel = lambda item: str(item.relative_to(FOLDER))
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': rel(SCRIPT), 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': rel(positive_log), 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': rejected.returncode,
            'negative_expected_error': expected,
            'negative_log': rel(negative_log), 'negative_log_sha256': sha(negative_log),
            'proof_scope': 'Source join and synthetic-as-physical rejection; no physical or legal claim'}
        print(suffix, 'independent audit pass/reject', flush=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
