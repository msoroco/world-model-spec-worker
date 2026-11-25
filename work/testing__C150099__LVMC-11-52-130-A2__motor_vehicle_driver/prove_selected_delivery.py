"""Bind exact-case CPU delivery audit and diagnostic-source rejection proofs."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / 'selected_delivery.py'
ERROR = 'synthetic saved source cannot satisfy original delivery'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        attempt = REPO / '.runtime-work' / ('c150099-saved-proof-' + suffix +
                                            '-v6/v0001/analysis')
        base = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT),
                '--attempt', str(attempt), '--case', case]
        positive = base + ['--allow-diagnostic']
        negative = base
        success = subprocess.run(positive, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        failure = subprocess.run(negative, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        positive_log = ROOT / ('cpu-selected-delivery-' + suffix + '.log')
        negative_log = ROOT / ('cpu-selected-delivery-negative-' + suffix + '.log')
        positive_log.write_text(success.stdout.rstrip() + '\n')
        negative_log.write_text(failure.stdout.rstrip() + '\n')
        if success.returncode or failure.returncode == 0 or ERROR not in failure.stdout:
            raise ValueError('selected delivery proof failed: ' + suffix + '\n' +
                             success.stdout[-800:] + failure.stdout[-800:])
        result = json.loads(success.stdout)
        if result['case_id'] != case or result['diagnostic_fixture'] is not True or \
                result['physical_acceptance_claimed'] is not False:
            raise ValueError('selected delivery test overclaims: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': shlex.join(positive), 'negative_command': shlex.join(negative),
            'test_exit_code': 0, 'negative_exit_code': failure.returncode,
            'negative_expected_error': ERROR,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_log': negative_log.name, 'negative_log_sha256': sha(negative_log),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
        print('selected delivery diagnostic and rejection passed:', suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
