"""Bind independent diagnostic delivery-positive/source-negative CPU proofs."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(args.scratch.resolve() / 'output'),
               TMPDIR=str(args.scratch.resolve() / 'tmp'))
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        base = [sys.executable, str(folder / 'prove_delivery_audit.py'), case_id,
                '--scratch', str(args.scratch)]
        logs = []
        for negative in (False, True):
            command = base + (['--negative'] if negative else [])
            proc = subprocess.run(command, capture_output=True, text=True, env=env)
            log = folder / 'cases' / suffix / ('delivery-negative.log' if negative else 'delivery-positive.log')
            log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')
            if (not negative and proc.returncode != 0) or (negative and proc.returncode == 0):
                raise RuntimeError(str(log) + ': ' + log.read_text())
            logs.append((command, proc.returncode, log))
        expected = 'complete original participant/trace/frame count missing'
        assert expected in logs[1][2].read_text()
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'test_exit_code': 0, 'negative_exit_code': logs[1][1],
            'negative_expected_error': expected,
            'command': ' '.join(logs[0][0]),
            'negative_command': ' '.join(logs[1][0]),
            'script': 'prove_delivery_audit.py',
            'script_sha256': sha(folder / 'prove_delivery_audit.py'),
            'test_log': str(logs[0][2].relative_to(folder)),
            'test_log_sha256': sha(logs[0][2]),
            'negative_log': str(logs[1][2].relative_to(folder)),
            'negative_log_sha256': sha(logs[1][2]),
            'scope': 'Source-bound synthetic diagnostic; actual Native and legal acceptance remain future checks.'}
        print(suffix, 'delivery diagnostic positive/negative passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
