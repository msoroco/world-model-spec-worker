"""Refresh exact unselected offline and synthetic package proofs after Native edits."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'


def run():
    data = json.loads(MANIFEST.read_text())
    if data['status'] != 'draft_not_selected' or len(data['cases']) != 2:
        raise ValueError('Expected two unselected controlled cases')
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(prefix='c110454-frame-proof-', dir=ROOT / '.runtime-work'))
    for entry in data['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE / 'draft-candidates' / suffix / candidate
            command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline', '--manifest', str(MANIFEST),
                       '--case', entry['case_id'], '--candidate', candidate,
                       '--output', str(scratch / (suffix + '-' + candidate)), '--python', str(PYTHON)]
            offline = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            if offline.returncode:
                raise RuntimeError('Offline failed for ' + suffix + '/' + candidate + ': ' + offline.stdout)
            receipt = json.loads(offline.stdout)
            shutil.copyfile(scratch / (suffix + '-' + candidate) / 'offline.log', folder / 'offline.log')
            (folder / 'command-offline.log').write_text(json.dumps(receipt, indent=2) + '\n')
            probe = subprocess.run([str(PYTHON), str(HERE / 'probe-package-compatibility.py'),
                                    '--suffix', suffix, '--candidate', candidate],
                                   cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=600)
            (folder / 'compatibility.log').write_text(probe.stdout)
            if probe.returncode:
                raise RuntimeError('Compatibility failed for ' + suffix + '/' + candidate + ': ' + probe.stdout)
            lines = probe.stdout.splitlines()
            package = json.loads('\n'.join(lines[1:]))
            work = Path(lines[0].removeprefix('scratch '))
            shutil.copyfile(work / 'output/compatibility.json', folder / 'diagnostic-compatibility.json')
            shutil.copyfile(work / 'negative-analysis.log', folder / 'negative-analysis.log')
            output = work / 'output'
            shutil.copyfile(output / 'compatibility-analysis.log', folder / 'analysis-compatibility.log')
            print(suffix, candidate, 'offline and package passed', flush=True)


if __name__ == '__main__':
    run()
