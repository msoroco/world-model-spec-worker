"""Replay the four fresh synthetic compatibility attempts through recorded-only processing."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        attempt = REPO / '.runtime-work' / f'c158190-{suffix}-primary-compat-v4'
        output = REPO / '.runtime-work' / f'c158190-{suffix}-primary-saved-v4'
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)]
        env = dict(os.environ)
        env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c158190-output-root-20261111')
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        folder = (ROOT / entry['construction']).parent
        log = folder / 'primary-saved-current.log'
        log.write_text(result.stdout[-30000:] + result.stderr[-30000:])
        if result.returncode:
            raise ValueError(f'{suffix}: process-saved exited {result.returncode}; see {log}')
        receipt = output / 'v0001/processing.json'
        saved = json.loads(receipt.read_text())
        if not saved.get('recorded_only') or saved.get('physical_acceptance_claimed'):
            raise ValueError(f'{suffix}: saved receipt is not diagnostic-only')
        print(json.dumps({'case': suffix, 'recorded_only': True,
                          'physical_acceptance_claimed': False,
                          'receipt': str(receipt.relative_to(REPO))}), flush=True)


if __name__ == '__main__':
    main()
