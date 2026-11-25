"""Run and bind exact synthetic motion and capture-closure CPU fixtures."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def run(command, log):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c111125-owner/output')
    env['TMPDIR'] = str(REPO / '.runtime-work/c111125-owner/tmp')
    completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(completed.stdout.rstrip() + '\n')
    if completed.returncode:
        raise ValueError(f'fixture command failed ({completed.returncode}): {log}')
    return json.loads(completed.stdout)


def main():
    scratch = REPO / '.runtime-work/c111125-owner/physical'
    scratch.mkdir(parents=True, exist_ok=True)
    (REPO / '.runtime-work/c111125-owner/tmp').mkdir(parents=True, exist_ok=True)
    (REPO / '.runtime-work/c111125-owner/output').mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        construction = folder / 'delivery-construction.draft.json'
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / ('physical-' + kind + '.json')
            log = folder / ('physical-' + kind + '.log')
            command = [sys.executable, str(ROOT / 'prove_physical.py'),
                       '--case', case_id, '--kind', kind,
                       '--scratch', str(scratch), '--result', str(result)]
            observed = run(command, log)
            if observed['status'] != {'complete_motion': 'met',
                                      'incomplete_motion': 'not_met',
                                      'missing_evidence': 'unverified'}[kind]:
                raise ValueError('fixture outcome differs')
            fixtures.append({'kind': kind,
                             'command': ' '.join(command), 'exit_code': 0,
                             'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
        log = folder / 'physical-lifecycle.log'
        command = [sys.executable, str(ROOT / 'prove_lifecycle.py'),
                   '--case', case_id, '--scratch', str(scratch)]
        life = run(command, log)
        receipt = {'format': 'worker-physical-preparation-proof',
                   'case_id': case_id, 'construction_sha256': sha(construction),
                   'diagnostic_fixture': True,
                   'physical_acceptance_claimed': False,
                   'fixtures': fixtures,
                   'lifecycle': {'command': ' '.join(command),
                                 'events': life['events'], 'exit_code': 0,
                                 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}}
        write(folder / 'physical-preparation.draft.json', receipt)
    print(f'bound {len(plan["cases"])} exact synthetic physical and lifecycle proofs')


if __name__ == '__main__':
    main()
