"""Refresh exact construction offline receipts after selected source changes."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
NATIVE = FOLDER / 'native'


def main():
    draft = json.loads((NATIVE / 'draft-manifest.json').read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work'))
    for index, case in enumerate(draft['cases']):
        for candidate in ('primary', 'fallback1'):
            output = ROOT / f'.runtime-work/c229351-offline-v7-{index}-{candidate}'
            cmd = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'), 'offline',
                '--manifest', str(NATIVE / 'draft-manifest.json'), '--case', case['case_id'],
                '--candidate', candidate, '--output', str(output)]
            with (NATIVE / f'condition-{index}-{candidate}-offline.log').open('w') as log:
                status = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log,
                                        stderr=subprocess.STDOUT)
            if status.returncode:
                raise RuntimeError(f'Offline {index} {candidate} failed')
            shutil.copy2(output / 'offline.log',
                         NATIVE / f'condition-{index}-{candidate}-offline-tests.log')
            print(index, candidate, 'offline passed', flush=True)


if __name__ == '__main__':
    main()
