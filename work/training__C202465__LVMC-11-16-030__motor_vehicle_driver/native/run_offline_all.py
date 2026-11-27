"""Rerun exact current-runtime primary and fallback offline checks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / 'execution-manifest.json'
PYTHON = str(ROOT / '.venv-cpu/bin/python')


def run():
    data = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(ROOT / '.runtime-work'),
               MPLCONFIGDIR=str(ROOT / '.runtime-work/c202465-lvmc-mpl'))
    stamp = str(time.time_ns())
    for entry in data['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        for candidate in ('primary', 'fallback1'):
            output = ROOT / '.runtime-work' / ('c202465-lvmc-offline-'+suffix+'-'+candidate+'-'+stamp)
            command = [PYTHON, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--candidate', candidate, '--output', str(output),
                       '--python', PYTHON]
            result = subprocess.run(command, capture_output=True, text=True, env=env)
            if result.returncode:
                raise RuntimeError(suffix+' '+candidate+' offline failed: '+result.stderr[-1500:])
            source = output / 'offline.log'
            log = WORK / 'selected-offline-logs' / suffix / (candidate+'.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_bytes(source.read_bytes())
            target = entry if candidate == 'primary' else entry['candidates'][0]
            target['offline'] = {'command': ' '.join(command),
                                 'construction_sha256': target['construction_sha256'],
                                 'exit_code': 0, 'log': str(log.relative_to(WORK)),
                                 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
            print('PASS', suffix, candidate)
    MANIFEST.write_text(json.dumps(data, indent=2)+'\n')


if __name__ == '__main__':
    run()
