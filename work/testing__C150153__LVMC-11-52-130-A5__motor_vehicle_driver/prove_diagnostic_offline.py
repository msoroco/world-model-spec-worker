"""Run pinned exact-case offline checks for diagnostic primary/fallback bundles."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.diagnostic.json'
SCRATCH = ROOT / '.runtime-work' / 'c150153-diagnostic-offline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    receipts = []
    for entry in manifest['cases']:
        for candidate in ('primary', 'fallback1'):
            case_id = entry['case_id']
            name = case_id.removeprefix(HERE.name + '__')
            dest = SCRATCH / (name + '-' + candidate)
            if dest.exists():
                import shutil
                shutil.rmtree(dest)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--candidate', candidate, '--output', str(dest),
                       '--python', sys.executable]
            env = dict(os.environ)
            env['TMPDIR'] = str(ROOT / '.runtime-work' / 'c150153-owner' / 'tmp')
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / 'c150153-owner' / 'pipeline')
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(f'{name}/{candidate}: {run.stderr[-1500:]} {run.stdout[-1500:]}')
            proposal = entry if candidate == 'primary' else entry['candidates'][0]
            receipts.append({'case_id': case_id, 'candidate_id': candidate,
                             'construction_sha256': proposal['construction_sha256'],
                             'offline_log_sha256': sha(dest / 'offline.log'),
                             'offline_log': str(dest.relative_to(ROOT) / 'offline.log'),
                             'exit_code': 0, 'scope': 'diagnostic software preflight only'})
            print(f'{name}/{candidate}: offline passed')
    report = {'format': 'c150153-diagnostic-offline-index-v1',
              'assignment_id': HERE.name, 'manifest_sha256': sha(MANIFEST),
              'receipts': receipts, 'source_kind': 'synthetic_diagnostic',
              'physical_acceptance': False, 'legal_status': 'unresolved'}
    (HERE / 'diagnostic-offline-index.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
