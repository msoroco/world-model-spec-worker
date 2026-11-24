"""Refresh exact offline proof after construction source binding."""
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
    parser.add_argument('--tag', default='source-v2')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    scratch = args.scratch.resolve()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'output'),
               TMPDIR=str(scratch / 'tmp'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate_id, target in [('primary', entry),
                                     ('fallback1', entry['candidates'][0])]:
            output = scratch / (args.tag + '-offline-' + candidate_id + '-' + suffix)
            command = [sys.executable, 'runtime.py', 'offline', '--manifest',
                       str(manifest_path), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output)]
            proc = subprocess.run(command, capture_output=True, text=True, env=env)
            log = folder / 'cases' / suffix / (candidate_id + '-offline.log')
            log.write_text((proc.stdout + proc.stderr).rstrip() + '\n', encoding='utf-8')
            if proc.returncode:
                raise RuntimeError(suffix + ' ' + candidate_id + ': ' + log.read_text())
            target['offline'] = {'command': ' '.join(command),
                                 'construction_sha256': target['construction_sha256'],
                                 'exit_code': 0, 'log': str(log.relative_to(folder)),
                                 'log_sha256': sha(log)}
            print(suffix, candidate_id, 'offline passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')


if __name__ == '__main__':
    main()
