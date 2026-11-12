"""Run the pinned runtime offline command for all 16 staged sweep bundles."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(tag):
    manifest_path = HERE / 'sweep-execution-candidate.json'
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', *(item['id'] for item in entry['candidates'])):
            output = REPO / '.runtime-work' / f'c111256-{tag}-runtime-offline-all' / suffix / candidate
            if output.exists():
                raise ValueError('Retain prior runtime offline output; use a fresh tag')
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(manifest_path), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output),
                       '--python', str(PYTHON)]
            run = subprocess.run(command, cwd=REPO, capture_output=True,
                                 text=True, timeout=300)
            if run.returncode:
                raise ValueError(f'Runtime offline failed {suffix} {candidate}: {run.stdout[-900:]}{run.stderr[-900:]}')
            response = json.loads(run.stdout)
            if response['offline_passed'] is not True or response['simulation_started'] is not False:
                raise ValueError('Runtime offline response differs')
            dest = HERE / f'{tag}-sweep-offline' / suffix / (candidate + '.log')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output / 'offline.log', dest)
            selected = json.loads((output / 'candidate-selection.json').read_text())
            if (selected['manifest_sha256'] != sha(manifest_path) or
                    selected['case_id'] != entry['case_id'] or
                    selected['candidate_id'] != candidate):
                raise ValueError('Runtime offline selected the wrong sweep source')
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'log': dest.relative_to(HERE).as_posix(),
                         'log_sha256': sha(dest), 'exit_code': 0})
    receipt = {'format': 'c111256-unselected-sweep-runtime-offline-v1',
               'manifest_sha256': sha(manifest_path), 'rows': rows,
               'offline_passed': len(rows), 'selected': False,
               'simulation_started': False}
    path = HERE / f'{tag}-sweep-runtime-offline-matrix.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'offline_passed': len(rows), 'matrix_sha256': sha(path),
                      'selected': False, 'simulation_started': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='update028')
    main(parser.parse_args().tag)
