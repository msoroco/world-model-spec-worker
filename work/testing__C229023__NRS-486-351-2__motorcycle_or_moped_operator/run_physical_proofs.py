"""Run exact-case synthetic motion and lifecycle CPU proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229023-owner-nov26/physical'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def run(command, log):
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c229023-owner-nov26')
    env['TMPDIR'] = str(REPO / '.runtime-work/c229023-owner-nov26')
    process = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(process.stdout.rstrip() + '\n')
    if process.returncode:
        raise ValueError(f'{command} failed: {process.stdout[-1000:]}')
    return process.returncode


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            log = folder / f'physical-{kind}.log'
            result = folder / f'physical-{kind}.json'
            command = [sys.executable, str(ROOT / 'prove_physical.py'),
                       '--case', case, '--kind', kind,
                       '--scratch', str(SCRATCH), '--result', str(result)]
            code = run(command, log)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': code,
                             'log': str(log.relative_to(ROOT)),
                             'log_sha256': sha(log),
                             'result': str(result.relative_to(ROOT)),
                             'result_sha256': sha(result)})
        life_log = folder / 'physical-lifecycle.log'
        life_cmd = [sys.executable, str(ROOT / 'prove_lifecycle.py'),
                    '--case', case, '--scratch', str(SCRATCH)]
        code = run(life_cmd, life_log)
        life = json.loads(life_log.read_text())
        receipt = folder / 'physical-preparation.json'
        write(receipt, {'format': 'worker-physical-preparation', 'case_id': case,
                        'construction_sha256': entry['construction_sha256'],
                        'fixtures': fixtures,
                        'lifecycle': {'events': life['events'], 'exit_code': code,
                                      'command': ' '.join(life_cmd),
                                      'log': str(life_log.relative_to(ROOT)),
                                      'log_sha256': sha(life_log)}})
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(ROOT)),
                                         'sha256': sha(receipt)}
        print(case, 'physical/lifecycle passed')
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
