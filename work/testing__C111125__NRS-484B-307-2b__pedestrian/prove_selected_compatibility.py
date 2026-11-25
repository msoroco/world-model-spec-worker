"""Run pinned offline and positive/negative compatibility for selected plans."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c111125-owner'


def run(command):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'output')
    env['TMPDIR'] = str(SCRATCH / 'tmp')
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError('Pinned command failed: ' + ' '.join(command) + '\n' + result.stdout[-3000:])
    return result.stdout


def main():
    (SCRATCH / 'tmp').mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'output').mkdir(parents=True, exist_ok=True)
    manifest = ROOT / 'execution-manifest.draft.json'
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        candidates = ['primary'] if suffix in ('other_device_stop', 'flashing_no_countdown_wait') else ['primary', 'fallback1']
        for candidate in candidates:
            tag = 'delivery' if candidate == 'primary' else candidate
            output = SCRATCH / ('selected-offline-' + suffix + '-' + tag + '-v7')
            if output.exists():
                raise ValueError('retain prior offline output: ' + str(output))
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(manifest), '--case', case_id,
                       '--output', str(output)]
            if candidate != 'primary':
                command += ['--candidate', candidate]
            text = run(command)
            log = folder / ('delivery-offline-draft.log' if candidate == 'primary'
                            else 'fallback1-offline.log')
            log.write_text(text.rstrip() + '\n')
            output = SCRATCH / ('selected-compat-' + suffix + '-' + tag + '-v7')
            if output.exists():
                raise ValueError('retain prior compatibility output: ' + str(output))
            command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                       '--manifest', str(manifest), '--case', case_id,
                       '--output', str(output),
                       '--library', str(REPO / 'runtime/library'),
                       '--validator', str(SCRATCH / 'validator/.lake/build/bin/adapterCheck')]
            if candidate != 'primary':
                command += ['--candidate', candidate]
            run(command)
            if candidate == 'primary':
                names = ('delivery-compatibility-draft.json',
                         'delivery-compatibility-analysis-draft.log',
                         'delivery-compatibility-negative-draft.log')
            else:
                names = ('fallback1-compatibility.json',
                         'fallback1-compatibility-analysis.log',
                         'fallback1-compatibility-negative.log')
            for source, name in zip(('compatibility.json', 'compatibility-analysis.log',
                                     'negative-analysis.log'), names):
                shutil.copyfile(output / source, folder / name)
            receipt = json.loads((folder / names[0]).read_text())
            if receipt['passed'] is not True or receipt['candidate_id'] != candidate:
                raise ValueError('candidate compatibility differs: ' + case_id)
            print(f'{suffix} {candidate}: offline and compatibility passed', flush=True)


if __name__ == '__main__':
    main()
