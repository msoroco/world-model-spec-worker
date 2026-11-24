"""Rerun all eight unselected exit-side constructions with the current runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'draft-execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'draft_not_selected' or len(manifest['cases']) != 2:
        raise ValueError('This proof is limited to the unselected two-case draft')
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c329610-current')
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c329610-current-offline-') as temp:
        for entry in manifest['cases']:
            for candidate_id in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                candidate = entry if candidate_id == 'primary' else next(
                    x for x in entry['candidates'] if x['id'] == candidate_id)
                construction = HERE / candidate['construction']
                if sha(construction) != candidate['construction_sha256']:
                    raise ValueError('Draft construction hash changed')
                output = Path(temp) / (entry['case_id'].split('__')[-1] + '-' + candidate_id)
                command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                           '--manifest', str(MANIFEST), '--case', entry['case_id'],
                           '--candidate', candidate_id, '--output', str(output),
                           '--python', str(PYTHON)]
                run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=300)
                if run.returncode or not (output / 'offline.log').is_file():
                    raise ValueError(f'Current offline failed: {entry["case_id"]} '
                                     f'{candidate_id}: {run.stdout[-1200:]}')
                receipt = json.loads(run.stdout)
                if receipt.get('offline_passed') is not True or receipt.get('simulation_started') is not False:
                    raise ValueError('Current offline result is not a CPU-only pass')
                rows.append({'case_id': entry['case_id'], 'candidate_id': candidate_id,
                             'construction_sha256': candidate['construction_sha256'],
                             'offline_log_sha256': sha(output / 'offline.log'),
                             'exit_code': run.returncode, 'offline_passed': True,
                             'simulation_started': False})
    return {'format': 'c329610-current-unselected-offline-proof-v1',
            'passed': True, 'manifest_sha256': sha(MANIFEST),
            'case_count': 2, 'construction_count': len(rows), 'rows': rows,
            'selected_delivery_case_count': 0, 'native_executed': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
