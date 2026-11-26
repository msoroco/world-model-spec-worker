"""Recheck all exact selected construction candidates after finalizer changes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c10052-disposition-offline-all'
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(source, destination):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text('\n'.join(lines) + '\n')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    env['TMPDIR'] = str(SCRATCH)
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        for candidate in [case] + case['candidates']:
            ident = candidate.get('id', 'primary')
            prior = candidate.get('offline', {})
            if (prior.get('construction_sha256') == candidate['construction_sha256']
                    and prior.get('exit_code') == 0 and prior.get('log')
                    and (ROOT / prior['log']).is_file()
                    and sha(ROOT / prior['log']) == prior.get('log_sha256')):
                print(suffix, ident, 'offline retained', flush=True)
                continue
            output = SCRATCH / f'{suffix}-{ident}'
            if output.exists():
                shutil.rmtree(output)
            command = [str(PYTHON), 'runtime.py', 'offline', '--manifest',
                       str(MANIFEST.relative_to(REPO)), '--case', case['case_id'],
                       '--output', str(output), '--python', str(PYTHON)]
            if ident != 'primary':
                command += ['--candidate', ident]
            result = subprocess.run(command, cwd=REPO, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{suffix}/{ident} offline failed: {result.stdout[-1200:]}')
            folder = ROOT / Path(candidate['construction']).parent
            log = folder / 'offline.log'
            clean_log(output / 'offline.log', log)
            candidate['offline'] = {
                'command': ' '.join(command[:-2]) if ident == 'primary' else ' '.join(command),
                'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                'log_sha256': sha(log),
            }
            print(suffix, ident, 'offline passed', flush=True)
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
