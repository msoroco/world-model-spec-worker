"""Run eight exact unselected C405647 bundles through pinned CPU offline."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
MANIFEST = FOLDER / 'draft-execution-manifest.json'
PYTHON = (ROOT / '.venv-cpu/bin/python').resolve()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    data = json.loads(MANIFEST.read_text())
    assert data['status'] == 'draft_not_selected' and len(data['cases']) == 2
    assert PYTHON.is_file()
    env = dict(os.environ)
    geos = str(ROOT / '.runtime-work/geos-wheel/shapely.libs')
    env['LD_LIBRARY_PATH'] = geos + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    run_root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c405647-1a-offline-'))
    receipts = []
    for entry in data['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            destination = run_root / (suffix + '-' + candidate)
            command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(destination),
                       '--python', str(PYTHON)]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=300)
            folder = FOLDER / 'draft-candidates' / suffix / candidate
            command_log = folder / 'draft-command.log'
            command_log.write_text(result.stdout)
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            receipt = {'case_id': entry['case_id'], 'candidate_id': candidate,
                       'command': command, 'exit_code': result.returncode,
                       'command_log': str(command_log.relative_to(FOLDER)),
                       'command_log_sha256': _sha(command_log),
                       'construction_sha256': ref['construction_sha256'],
                       'scope': 'exact unselected CPU offline only; no Native or delivery acceptance'}
            if (destination / 'offline.log').is_file():
                unit_log = folder / 'unit-test.log'
                shutil.copyfile(destination / 'offline.log', unit_log)
                receipt.update(unit_log=str(unit_log.relative_to(FOLDER)),
                               unit_log_sha256=_sha(unit_log))
            (folder / 'draft-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            receipts.append(receipt)
            print(suffix, candidate, 'exit', result.returncode, flush=True)
    (FOLDER / 'draft-offline-summary.json').write_text(json.dumps({
        'format': 'unselected-draft-offline-summary-v1',
        'runtime_manifest_sha256': data['runtime_manifest_sha256'],
        'results': receipts}, indent=2) + '\n')
    if any(row['exit_code'] for row in receipts):
        raise SystemExit(1)


if __name__ == '__main__':
    run()
