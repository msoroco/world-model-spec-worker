"""Bind exact-case selected delivery diagnostics and original-source rejection."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
AUDIT = ROOT / 'selected_delivery.py'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work/c158190-nov27-saved-v1/tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c158190-nov27-saved-v1/output'))
    process = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(process.stdout.rstrip() + '\n')
    return process.returncode


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        attempt = REPO / '.runtime-work' / ('c158190-saved-proof-' + suffix + '-v12') / 'v0001/analysis'
        base = [str(REPO / '.venv-cpu/bin/python'), str(AUDIT), '--attempt', str(attempt),
                '--case', case]
        positive = ROOT / ('cpu-selected-delivery-' + suffix + '.log')
        negative = ROOT / ('cpu-selected-delivery-negative-' + suffix + '.log')
        good_code = run(base + ['--allow-diagnostic'], positive)
        bad_code = run(base, negative)
        expected = 'synthetic saved source cannot satisfy original delivery'
        if good_code != 0 or bad_code == 0 or expected not in negative.read_text():
            raise ValueError('selected diagnostic/rejection proof failed: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': AUDIT.name, 'script_sha256': sha(AUDIT),
            'command': ' '.join(base + ['--allow-diagnostic']),
            'test_exit_code': good_code, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': ' '.join(base),
            'negative_exit_code': bad_code, 'negative_expected_error': expected,
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
        }
        print('selected audit passed/rejected:', suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
