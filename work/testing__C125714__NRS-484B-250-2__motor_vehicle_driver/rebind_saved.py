"""Replay each selected case from a separate source-only current-revision tree."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from stage_saved_acquisition import stage


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--validator', type=Path, required=True)
    parser.add_argument('--tag', default='source-v2')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    scratch = args.scratch.resolve()
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'output'),
               TMPDIR=str(scratch / 'tmp'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        source = scratch / (args.tag + '-compat-primary-' + suffix)
        staged = scratch / (args.tag + '-source-' + suffix)
        output = scratch / (args.tag + '-saved-' + suffix)
        stage(source, staged, manifest_path)
        command = [sys.executable, 'runtime.py', 'process-saved',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--attempt', str(staged), '--output', str(output),
                   '--library', 'runtime/library', '--validator', str(args.validator)]
        proc = subprocess.run(command, capture_output=True, text=True, env=env)
        log = folder / 'cases' / suffix / 'process-saved-current.log'
        log.write_text((proc.stdout + proc.stderr).rstrip() + '\n', encoding='utf-8')
        if proc.returncode:
            raise RuntimeError(suffix + ': ' + log.read_text())
        entry['post_capture']['test_exit_code'] = 0
        entry['post_capture']['test_log_sha256'] = sha(log)
        entry['post_capture']['proof_scope'] = (
            'Current-runtime source-only synthetic diagnostic replay; '
            'physical Native review pending')
        print(suffix, 'current-revision saved-only passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')


if __name__ == '__main__':
    main()
