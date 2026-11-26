"""Rerun all selected and fallback offline checks against current bundles."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from parked_lamps import CASES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if {entry['case_id'] for entry in manifest['cases']} != {
            ASSIGNMENT + '__' + case.name for case in CASES}:
        raise ValueError('selected exact case inventory changed')
    scratch = ROOT / '.runtime-work/c229398-selected-offline'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c229398-output')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c229398-tmp')
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(ASSIGNMENT + '__')
        for candidate in ('primary', 'fallback1'):
            ref = entry if candidate == 'primary' else entry['candidates'][0]
            output = scratch / name / candidate
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                shutil.rmtree(output)
            command = ['.venv-cpu/bin/python', 'runtime.py', 'offline',
                       '--manifest', str(manifest_path), '--case', entry['case_id'],
                       '--output', str(output)]
            if candidate != 'primary':
                command.extend(['--candidate', candidate])
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, text=True)
            log = HERE / f'cpu-selected-offline-{name}-{candidate}.log'
            content = (result.stdout + result.stderr).rstrip() + '\n'
            log.write_text(content)
            if result.returncode:
                raise ValueError(f'{name}/{candidate} offline failed: {content[-1000:]}')
            ref['offline'] = {'command': ' '.join(command),
                              'construction_sha256': ref['construction_sha256'],
                              'exit_code': 0, 'log': log.name,
                              'log_sha256': sha(log)}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return len(manifest['cases']) * 2


if __name__ == '__main__':
    print(prove())
