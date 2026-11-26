"""Run each exact selected school-zone construction through the pinned offline gate."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c255451-offline-proof')
    env['MPLCONFIGDIR'] = str(REPO / '.runtime-work/c255451-mpl')
    (REPO / '.runtime-work/c255451-mpl').mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        output = REPO / '.runtime-work' / ('c255451-selected-offline-v6-' + condition)
        if output.exists():
            raise ValueError('Choose fresh offline output: ' + str(output))
        command = [sys.executable, '-B', 'runtime.py', 'offline',
                   '--manifest', str(MANIFEST.relative_to(REPO)),
                   '--case', entry['case_id'], '--output', str(output.relative_to(REPO))]
        proc = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                              text=True, timeout=180)
        log = HERE / 'selected' / condition / 'offline.log'
        log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')
        if proc.returncode != 0:
            raise RuntimeError('Offline failed for ' + condition + ': ' + log.read_text())
        entry['offline'] = {
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + entry['case_id']
                       + ' --output ' + str(output.relative_to(REPO)),
            'exit_code': 0,
            'construction_sha256': entry['construction_sha256'],
            'log': str(log.relative_to(ROOT)),
            'log_sha256': sha(log),
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'offline_selected_passed': len(manifest['cases'])}, sort_keys=True))


if __name__ == '__main__':
    main()
