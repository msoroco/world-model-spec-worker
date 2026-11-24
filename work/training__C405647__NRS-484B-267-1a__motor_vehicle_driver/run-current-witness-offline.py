"""Retain current-runtime offline receipts for selected witness constructions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-witness-manifest.json'
PUBLIC = HERE / 'current-public'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    env = dict(os.environ)
    env.update(SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c405647-1a-runtime-import'),
               TMPDIR=str(ROOT / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c405647-1a-selected-offline-') as temp:
        for suffix in ('witness_1', 'witness_2'):
            for candidate in ('primary', 'fallback1', 'fallback2'):
                case = HERE.name + '__' + suffix
                destination = Path(temp) / (suffix + '-' + candidate)
                command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'), 'offline',
                           '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
                           '--output', str(destination), '--python', str(ROOT / '.venv-cpu/bin/python')]
                done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                log = PUBLIC / (suffix + '-' + candidate + '-offline.log')
                log.write_text(done.stdout.rstrip() + '\n')
                if done.returncode:
                    raise ValueError(f'{suffix} {candidate} offline failed: {done.stdout[-800:]}')
                receipt = json.loads(done.stdout)
                if not receipt['offline_passed'] or receipt['simulation_started']:
                    raise ValueError('Offline receipt did not prove CPU only')
                rows.append({'case_id': case, 'candidate_id': candidate, 'exit_code': done.returncode,
                             'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                             'construction_sha256': (next(x for x in manifest['cases'] if x['case_id'] == case)['construction_sha256'] if candidate == 'primary' else next(y for x in manifest['cases'] if x['case_id'] == case for y in x['candidates'] if y['id'] == candidate)['construction_sha256']),
                             'simulation_started': False})
                print(suffix, candidate, done.returncode, flush=True)
    (PUBLIC / 'witness-offline-summary.json').write_text(json.dumps({'passed': True,
        'format': 'c405647-1a-current-witness-offline', 'rows': rows}, indent=2) + '\n')


if __name__ == '__main__':
    main()
