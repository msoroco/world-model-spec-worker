"""Run and retain pinned offline receipts for four unselected alley bundles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE/'draft-alley-execution-manifest.json'
PYTHON = ROOT/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    data = json.loads(MANIFEST.read_text())
    assert data['status'] == 'draft_not_selected' and len(data['cases']) == 1
    entry = data['cases'][0]
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(ROOT/'.runtime-work/geos-wheel/shapely.libs') + \
        os.pathsep + env.get('LD_LIBRARY_PATH', '')
    run_root = Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work', prefix='c10052-alley-offline-'))
    receipts = []
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        destination = run_root/ident
        command = [str(PYTHON), str(ROOT/'runtime.py'), 'offline', '--manifest',
                   str(MANIFEST), '--case', entry['case_id'], '--candidate', ident,
                   '--output', str(destination), '--python', str(PYTHON)]
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=300)
        directory = HERE/'draft-alley-candidates'/'probe_c_alley_entry'/ident
        command_log = directory/'draft-command.log'
        command_log.write_text(result.stdout)
        selected = entry if ident == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == ident)
        receipt = {'case_id': entry['case_id'], 'candidate_id': ident,
            'command': ' '.join(command), 'exit_code': result.returncode,
            'command_log': str(command_log.relative_to(HERE)),
            'command_log_sha256': sha(command_log),
            'construction_sha256': selected['construction_sha256'],
            'scope': 'exact unselected offline CPU bundle; no physical or delivery acceptance proof'}
        if (destination/'offline.log').is_file():
            unit_log = directory/'unit-test.log'
            shutil.copyfile(destination/'offline.log', unit_log)
            receipt.update(unit_log=str(unit_log.relative_to(HERE)),
                           unit_log_sha256=sha(unit_log))
        (directory/'draft-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        receipts.append(receipt)
        print(ident, result.returncode, flush=True)
    (HERE/'draft-alley-offline-summary.json').write_text(json.dumps({
        'format': 'unselected-alley-draft-offline-summary-v1',
        'runtime_manifest_sha256': data['runtime_manifest_sha256'],
        'results': receipts}, indent=2)+'\n')
    if any(receipt['exit_code'] for receipt in receipts):
        raise SystemExit(1)


if __name__ == '__main__':
    run()
