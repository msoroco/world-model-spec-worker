"""Record exact pinned offline checks for the separate fallback diagnostic draft."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.fallback-diagnostic.json'
SCRATCH = ROOT / '.runtime-work/c150153-owner/fallback-offline'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'synthetic_fallback_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('offline proof requires unselected synthetic fallback draft')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        kind = entry['case_id'].removeprefix(HERE.name + '__')
        for candidate_id in ('primary', 'fallback1'):
            candidate = entry if candidate_id == 'primary' else entry['candidates'][0]
            output = SCRATCH / (kind + '-' + candidate_id)
            if output.exists():
                raise ValueError('fresh offline output required: ' + str(output))
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output),
                       '--python', sys.executable]
            env = dict(os.environ)
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env['TMPDIR'] = str(ROOT / '.runtime-work/c150153-owner/tmp')
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c150153-owner/pipeline')
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
            if run.returncode or 'offline_passed' not in run.stdout:
                raise RuntimeError(kind + '/' + candidate_id + ': ' + run.stdout[-1000:] + run.stderr[-1000:])
            saved_log = HERE / ('cpu-fallback-offline-' + kind + '-' + candidate_id + '.log')
            shutil.copy2(output / 'offline.log', saved_log)
            candidate['offline'] = {'exit_code': 0,
                                    'construction_sha256': candidate['construction_sha256'],
                                    'command': 'runtime.py offline --case ' + entry['case_id'] +
                                               ' --candidate ' + candidate_id,
                                    'log': saved_log.name,
                                    'log_sha256': sha(saved_log)}
            print(kind, candidate_id, 'offline passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    prove()
