"""Run selected pedestrian constructions without starting Native."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MANIFEST = HERE / 'selected-probe-manifest.json'
SCRATCH = ROOT / '.runtime-work' / 'c2281333079c' / 'selected-offline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    python = ROOT / '.venv-cpu/bin/python'
    count = 0
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for ref in [entry] + entry['candidates']:
            candidate = ref['id']
            target = SCRATCH / f'{suffix}-{candidate}-{ref["construction_sha256"][:12]}'
            command = [str(python), str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(target), '--python', str(python)]
            if not target.exists():
                result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                        capture_output=True, timeout=300)
                if result.returncode:
                    raise RuntimeError(f'{suffix}/{candidate}: {result.stderr[-1200:]}')
            internal = target / 'offline.log'
            if not internal.is_file() or 'OK' not in internal.read_text():
                raise RuntimeError(f'{suffix}/{candidate}: offline tests did not pass')
            returned = HERE / 'selected-offline' / f'{suffix}-{candidate}.log'
            returned.parent.mkdir(exist_ok=True)
            returned.write_text(internal.read_text().rstrip() + '\n')
            ref['offline'] = {'case_id': entry['case_id'], 'candidate_id': candidate,
                              'construction_sha256': ref['construction_sha256'],
                              'command': ' '.join(command), 'exit_code': 0,
                              'log': returned.relative_to(HERE).as_posix(),
                              'log_sha256': sha(returned)}
            count += 1
    write(MANIFEST, manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'offline_constructions_passed': count, 'simulation_started': False}))


if __name__ == '__main__':
    main()
