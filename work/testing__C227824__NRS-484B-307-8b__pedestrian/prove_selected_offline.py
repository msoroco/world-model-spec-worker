"""Prove source-gated selected primary and fallback bundles without CARLA."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c227824-selected-offline'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work/c227824-selected-tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c227824-selected-output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.removeprefix(HERE.name + '__')
        for candidate in ('primary', 'fallback1'):
            ref = entry if candidate == 'primary' else entry['candidates'][0]
            output = SCRATCH / suffix / candidate
            if output.exists():
                shutil.rmtree(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', cid,
                       '--output', str(output)]
            if candidate != 'primary':
                command.extend(['--candidate', candidate])
            done = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            log = HERE / ('cpu-selected-offline-' + suffix + '-' + candidate + '.log')
            log.write_text((done.stdout + done.stderr).rstrip() + '\n')
            if done.returncode:
                raise ValueError(cid + '/' + candidate + ' exact offline failed: ' + log.read_text()[-1000:])
            ref['offline'] = {'command': ' '.join(command),
                              'construction_sha256': ref['construction_sha256'],
                              'exit_code': 0, 'log': log.name, 'log_sha256': sha(log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases']) * 2


if __name__ == '__main__':
    print(prove())
