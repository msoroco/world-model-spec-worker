"""Run the pinned offline construction check for every rail candidate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    scratch = ROOT / '.runtime-work' / ('c202465-offline-candidates-' +
                                       sha(HERE / 'execution-manifest.json')[:12])
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work' / 'c202465'))
    receipts = []
    for suffix in VARIANTS:
        for candidate in ('primary', 'fallback1'):
            case = HERE.name + '__' + suffix
            dest = scratch / (suffix + '-' + candidate)
            if dest.exists():
                raise ValueError('Retain prior attempt; use a fresh offline scratch root: ' + str(dest))
            command = [sys.executable, '-B', str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(HERE / 'execution-manifest.json'), '--case', case,
                       '--output', str(dest), '--python', sys.executable,
                       '--candidate', candidate]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = HERE / ('selected-' + suffix + '-' + candidate + '-offline.log')
            log.write_text(result.stdout.rstrip() + '\n')
            receipts.append({'case_id': case, 'candidate': candidate,
                             'exit_code': result.returncode, 'log': log.name,
                             'log_sha256': sha(log)})
    path = HERE / 'candidate-proof-receipts.json'
    path.write_text(json.dumps({'format': 'rail-offline-candidate-proofs',
                                'receipts': receipts}, indent=2) + '\n')
    return {'passed': all(r['exit_code'] == 0 for r in receipts),
            'candidate_count': len(receipts), 'proof_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(run()))
