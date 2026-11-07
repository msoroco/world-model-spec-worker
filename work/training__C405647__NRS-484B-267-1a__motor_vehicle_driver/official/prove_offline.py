"""Run every official-branch candidate through the exact pinned offline CLI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MANIFEST = HERE / 'package-manifest.json'
PYTHON = (REPO / '.venv-cpu/bin/python').resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    data = json.loads(MANIFEST.read_text())
    assert len(data['cases']) == 2 and PYTHON.is_file()
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(REPO / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env['PATH'] = str(REPO / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    work = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work', prefix='c405647-official-offline-'))
    receipts = []
    for entry in data['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            destination = work / (suffix + '-' + candidate)
            command = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--candidate', candidate, '--output', str(destination),
                       '--python', str(PYTHON)]
            result = subprocess.run(command, cwd=REPO, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=300)
            folder = HERE / 'cpu-receipts' / suffix / candidate
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'command.log').write_text(result.stdout)
            unit_log = destination / 'offline.log'
            if unit_log.is_file():
                shutil.copyfile(unit_log, folder / 'offline.log')
            ref = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            receipt = {'case_id': case_id, 'candidate_id': candidate,
                       'command': command, 'exit_code': result.returncode,
                       'construction_sha256': ref['construction_sha256'],
                       'command_log_sha256': sha(folder / 'command.log'),
                       'unit_log_sha256': sha(folder / 'offline.log') if unit_log.is_file() else None,
                       'simulation_started': False,
                       'scope': 'exact pinned offline only; unselected CPU construction'}
            (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            receipts.append(receipt)
            print(suffix, candidate, result.returncode, flush=True)
    summary = {'format': 'c405647-official-pinned-offline-v1',
               'manifest_sha256': sha(MANIFEST), 'receipts': receipts}
    (HERE / 'cpu-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if any(r['exit_code'] for r in receipts):
        raise SystemExit(1)


if __name__ == '__main__':
    run()
