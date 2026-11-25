"""Rebind diagnostic attempts to the sealed canonical manifest, then process saved."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c111329-2871d-selected'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def run(cmd, log):
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c111329-runtime-output')
    env['TMPDIR'] = str(REPO / '.runtime-work/c111329-temp')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run(cmd, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    Path(log).write_text(result.stdout.rstrip() + '\n')
    if result.returncode:
        raise RuntimeError(f'failed: {cmd}: {result.stdout[-2000:]}')
    return json.loads(result.stdout)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        attempt = SCRATCH / f'{suffix}-sealed-compat'
        output = SCRATCH / f'{suffix}-sealed-saved'
        run([sys.executable, 'runtime.py', 'compatibility', '--manifest',
             str(MANIFEST.relative_to(REPO)), '--case', case, '--output',
             str(attempt.relative_to(REPO)), '--library', 'runtime/library',
             '--validator', str(VALIDATOR.relative_to(REPO))],
            ROOT / f'cpu-sealed-{suffix}-compat.log')
        result = run([sys.executable, 'runtime.py', 'process-saved', '--manifest',
             str(MANIFEST.relative_to(REPO)), '--case', case, '--attempt',
             str(attempt.relative_to(REPO)), '--output', str(output.relative_to(REPO)),
             '--library', 'runtime/library', '--validator', str(VALIDATOR.relative_to(REPO))],
            ROOT / f'cpu-sealed-{suffix}-saved.log')
        assert result['passed'] and result['recorded_only'] and not result['physical_acceptance_claimed']
        print(suffix, 'canonical saved-only pass', flush=True)

if __name__ == '__main__':
    main()
