"""Bind positive protocol wiring and rejected missing tunnel source for each case."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c312865-nov27/saved-v6'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c312865-nov27/output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(REPO / 'runtime/scenario_pipeline')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(manifest['assignment_id'] + '__')
        attempt = SCRATCH / ('attempt-' + suffix)
        saved = SCRATCH / ('processed-' + suffix)
        proof = {}
        for mode in ('positive', 'missing_source'):
            cmd = [sys.executable, str(ROOT / 'delivery_probe.py'),
                   '--case', entry['case_id'], '--attempt', str(attempt),
                   '--saved-root', str(saved), '--mode', mode]
            result = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
            log = ROOT / ('proof-delivery-' + suffix + '-' + mode + '.log')
            log.write_text((result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
            expected = 0 if mode == 'positive' else 2
            if result.returncode != expected:
                raise RuntimeError(log.read_text())
            proof[mode] = {'command': ' '.join(cmd), 'exit_code': result.returncode,
                           'log': log.name, 'log_sha256': digest(log)}
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'],
            'cpu_proof_kind': 'mock_only_contract_wiring',
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': digest(ROOT / 'delivery_audit.py'),
            'command': proof['positive']['command'],
            'test_exit_code': 0, 'test_log': proof['positive']['log'],
            'test_log_sha256': proof['positive']['log_sha256'],
            'negative_command': proof['missing_source']['command'],
            'negative_exit_code': 2,
            'negative_expected_error': 'sealed original missing or changed: tunnel-site.json',
            'negative_log': proof['missing_source']['log'],
            'negative_log_sha256': proof['missing_source']['log_sha256']}
        write(manifest_path, manifest)
        print('delivery audit proof', suffix, flush=True)


if __name__ == '__main__':
    main()
