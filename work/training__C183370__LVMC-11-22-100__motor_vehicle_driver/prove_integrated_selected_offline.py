"""Run exact selected offline checks for all twelve integrated cases and fallbacks."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
LABEL = 'update156-integrated-selected'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    manifest_sha = sha(MANIFEST)
    rows = []
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/update156-integrated-offline-output')
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.removeprefix(HERE.name + '__')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            log = HERE / f'{LABEL}-{short}-{candidate}-offline.log'
            output = REPO / '.runtime-work' / f'{LABEL}-{short}-{candidate}-offline'
            if log.exists() or output.exists():
                raise ValueError('Retain previous exact offline proof: ' + short + '/' + candidate)
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case,
                       '--candidate', candidate, '--output', str(output),
                       '--python', sys.executable]
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=REPO, env=env,
                                         stdout=stream, stderr=subprocess.STDOUT)
            if process.returncode:
                raise RuntimeError('Offline failed: ' + short + '/' + candidate)
            selection = output / 'candidate-selection.json'
            selected_result = json.loads(selection.read_text())
            if (selected_result['manifest_sha256'] != manifest_sha or
                    selected_result['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Offline selected another manifest or construction')
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'selection_sha256': sha(selection),
                         'log': log.name, 'log_sha256': sha(log),
                         'exit_code': 0})
        print(short, '4/4 offline passed', flush=True)
    matrix = HERE / (LABEL + '-forty-eight-offline-matrix.json')
    matrix.write_text(json.dumps({'format': 'worker-exact-selected-offline-matrix',
                                  'manifest_sha256': manifest_sha,
                                  'rows': rows}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'count': len(rows), 'manifest_sha256': manifest_sha,
                      'matrix_sha256': sha(matrix)}, sort_keys=True))


if __name__ == '__main__':
    main()
