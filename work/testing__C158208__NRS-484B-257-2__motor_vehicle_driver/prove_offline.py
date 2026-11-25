"""Run pinned offline primary and fallback checks for four exact cases."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c158208-nov25'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, TMPDIR=str(SCRATCH / 'tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
               PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        for candidate in ('primary', 'fallback1'):
            output = SCRATCH / ('offline-' + suffix + '-' + candidate + '-v6')
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'offline', '--manifest', str(manifest_path), '--case',
                       entry['case_id'], '--output', str(output), '--python',
                       str(REPO / '.venv-cpu/bin/python'), '--candidate', candidate]
            run = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = ROOT / ('cpu-offline-' + suffix + '-' + candidate + '.log')
            source = output / 'offline.log'
            log.write_text((source.read_text() if source.is_file() else run.stdout).rstrip() + '\n')
            if run.returncode:
                raise ValueError('offline failed: ' + suffix + '/' + candidate + '\n' + run.stdout[-1200:])
            receipt = {'command': shlex.join(command), 'exit_code': 0,
                       'construction_sha256': entry['construction_sha256'] if candidate == 'primary'
                       else entry['candidates'][0]['construction_sha256'],
                       'log': log.name, 'log_sha256': sha(log)}
            if candidate == 'primary':
                entry['offline'] = receipt
            else:
                entry['candidates'][0]['offline'] = receipt
            print('offline passed:', suffix, candidate, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
