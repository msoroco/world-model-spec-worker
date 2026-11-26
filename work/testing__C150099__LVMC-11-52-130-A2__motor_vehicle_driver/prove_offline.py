"""Run the pinned offline CLI for each exact diagnostic construction."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        destination = REPO / '.runtime-work' / 'c150099-nov25-offline-batch-v7' / suffix
        if destination.exists():
            raise ValueError('retain prior offline attempt; choose new proof version')
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'offline', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--output', str(destination), '--python',
                   str(REPO / '.venv-cpu/bin/python')]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = run.stdout.rstrip() + '\n'
        log = ROOT / ('cpu-offline-' + suffix + '.log')
        log.write_text(text)
        if run.returncode:
            raise ValueError('offline failed for ' + suffix + ': ' + text[-800:])
        entry['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                            'log': log.name,
                            'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                            'construction_sha256': entry['construction_sha256']}
        fallback = entry['candidates'][0]
        alternate = REPO / '.runtime-work' / 'c150099-nov25-offline-batch-v7' / (suffix + '-fallback1')
        command += ['--candidate', 'fallback1']
        command[command.index('--output') + 1] = str(alternate)
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        alternate_log = ROOT / ('cpu-offline-fallback-' + suffix + '.log')
        alternate_log.write_text(run.stdout.rstrip() + '\n')
        if run.returncode:
            raise ValueError('fallback offline failed for ' + suffix + ': ' + run.stdout[-800:])
        fallback['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                               'log': alternate_log.name,
                               'log_sha256': hashlib.sha256(alternate_log.read_bytes()).hexdigest(),
                               'construction_sha256': fallback['construction_sha256']}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('exact diagnostic offline proofs:', len(manifest['cases']))


if __name__ == '__main__':
    main()
