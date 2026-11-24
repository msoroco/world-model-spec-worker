"""Run every unselected C230241 reference candidate through pinned offline."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
CASE_ID = CASE.name + '__reference'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    matrix_path = HERE / 'fallback-matrix.json'
    manifest = CASE / 'draft-fallback-manifest.json'
    matrix = json.loads(matrix_path.read_text())
    assert matrix['manifest_sha256'] == sha(manifest)
    rows = []
    for row in matrix['candidates']:
        candidate = row['id']
        construction = CASE / row['construction']
        assert sha(construction) == row['construction_sha256']
        output = ROOT / '.runtime-work' / 'c230241-fallback-offline' / candidate
        output.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(
            ROOT / '.runtime-work' / 'c230241-fallback-pipeline')
        command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                   '--manifest', str(manifest), '--case', CASE_ID,
                   '--candidate', candidate, '--output', str(output)]
        process = subprocess.run(command, cwd=ROOT, env=env,
                                 capture_output=True, text=True, timeout=300)
        log = HERE / ('fallback-' + candidate + '-offline.log')
        log.write_text(process.stdout + process.stderr)
        if process.returncode:
            raise RuntimeError(candidate + ' offline failed: ' + process.stderr[-1000:])
        response = json.loads(process.stdout)
        assert response['offline_passed'] and response['simulation_started'] is False
        selection = json.loads((output / 'candidate-selection.json').read_text())
        assert selection['construction_sha256'] == row['construction_sha256']
        test_log = output / 'offline.log'
        assert 'Ran 4 tests' in test_log.read_text() and '\nOK\n' in test_log.read_text()
        rows.append({'candidate': candidate, 'construction_sha256': sha(construction),
                     'stdout_log_sha256': sha(log), 'test_log_sha256': sha(test_log),
                     'tests': 4, 'simulation_started': False})
    receipt = {'format': 'c230241-unselected-fallback-offline-v1',
               'case_id': CASE_ID, 'manifest_sha256': sha(manifest),
               'matrix_sha256': sha(matrix_path), 'rows': rows,
               'passed': True, 'original_native_observed': False,
               'physical_visibility_verified': False, 'delivery_ready': False,
               'prover_sha256': sha(Path(__file__))}
    destination = HERE / 'fallback-offline-proof.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'candidates': len(rows), 'tests': 4 * len(rows),
                      'receipt_sha256': sha(destination)}))


if __name__ == '__main__':
    main()
