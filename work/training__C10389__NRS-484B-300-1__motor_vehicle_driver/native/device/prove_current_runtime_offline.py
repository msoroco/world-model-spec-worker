"""Re-run the eight draft constructions through the pinned current runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = HERE / 'draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    scratch = ROOT / '.runtime-work' / 'c10389-offline-refresh'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'adapter')
    entries = []
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            destination = scratch / f"{case['case_id'].rsplit('__', 1)[1]}-{candidate}"
            if destination.exists():
                raise ValueError('Retain old offline output; choose fresh scratch')
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case['case_id'],
                       '--candidate', candidate, '--output', str(destination),
                       '--python', sys.executable]
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=330)
            if result.returncode:
                raise RuntimeError(f'{candidate} offline failed: {result.stderr[-2000:]}')
            log = destination / 'offline.log'
            entries.append({'case_id': case['case_id'],
                            'candidate_id': candidate,
                            'construction_sha256': sha(destination / 'construction.json'),
                            'offline_log_sha256': sha(log),
                            'test_count': log.read_text().count('Ran 3 tests'),
                            'passed': True})
    return {'format': 'c10389-pinned-current-runtime-offline-v1',
            'manifest_sha256': sha(MANIFEST), 'entries': entries,
            'passed_count': len(entries), 'simulation_started': False,
            'selected_delivery_claimed': False}


if __name__ == '__main__':
    proof = run()
    path = HERE / 'offline' / 'current-runtime-offline-8-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed_count': proof['passed_count'],
                      'proof_sha256': sha(path)}))
