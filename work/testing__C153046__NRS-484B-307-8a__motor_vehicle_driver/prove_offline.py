"""Run the pinned offline CLI for all eight exact red-left constructions."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, TMPDIR=str(REPO / '.runtime-work/c153046-nov25d/tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c153046-nov25d/output'),
               PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        output = REPO / '.runtime-work/c153046-nov25d' / ('offline-' + suffix + '-v12')
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'), 'offline',
                   '--manifest', str(manifest_path), '--case', case,
                   '--output', str(output), '--python', str(REPO / '.venv-cpu/bin/python')]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = ROOT / ('cpu-offline-' + suffix + '.log')
        log.write_text((output / 'offline.log').read_text().rstrip() + '\n'
                       if (output / 'offline.log').is_file() else run.stdout.rstrip() + '\n')
        if run.returncode:
            raise ValueError('offline failed: ' + suffix + '\n' + run.stdout[-1200:])
        entry['offline'] = {'command': shlex.join(command), 'exit_code': 0,
                            'construction_sha256': entry['construction_sha256'],
                            'log': log.name, 'log_sha256': sha(log)}
        print('offline passed:', suffix, flush=True)
        candidate = entry['candidates'][0]
        alternate = REPO / '.runtime-work/c153046-nov25d' / ('fallback-' + suffix + '-v8')
        fallback_command = command + ['--candidate', 'fallback1']
        fallback_command[fallback_command.index(str(output))] = str(alternate)
        fallback_run = subprocess.run(fallback_command, cwd=REPO, env=env, text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        fallback_log = ROOT / ('cpu-offline-fallback-' + suffix + '.log')
        fallback_log.write_text((alternate / 'offline.log').read_text().rstrip() + '\n'
                                if (alternate / 'offline.log').is_file()
                                else fallback_run.stdout.rstrip() + '\n')
        if fallback_run.returncode:
            raise ValueError('fallback offline failed: ' + suffix + '\n' + fallback_run.stdout[-1200:])
        candidate['offline'] = {'command': shlex.join(fallback_command), 'exit_code': 0,
                                'construction_sha256': candidate['construction_sha256'],
                                'log': fallback_log.name, 'log_sha256': sha(fallback_log)}
        print('fallback offline passed:', suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
