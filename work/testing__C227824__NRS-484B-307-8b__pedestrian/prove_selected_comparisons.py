"""Audit seven exact controlled pairs from selected saved diagnostic sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLAN = HERE / 'case-plan.json'
SCRIPT = HERE / 'comparison_audit.py'
SCRATCH = REPO / '.runtime-work/c227824-selected-comparisons'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads(PLAN.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work/c227824-selected-tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c227824-selected-output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    results = []
    for pair in plan['comparisons']:
        ident = pair['comparison_id']
        left, right = [REPO / '.runtime-work/c227824-selected-compat' /
                       cid.removeprefix(HERE.name + '__') / 'primary'
                       for cid in pair['case_ids']]
        output = SCRATCH / (ident + '.json')
        if output.exists():
            output.unlink()
        command = [sys.executable, str(SCRIPT), '--left-attempt', str(left),
                   '--right-attempt', str(right), '--comparison-id', ident,
                   '--plan', str(PLAN), '--output', str(output)]
        done = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                              text=True, timeout=600)
        log = HERE / ('cpu-selected-comparison-' + ident + '.log')
        log.write_text((done.stdout + done.stderr).rstrip() + '\n')
        if done.returncode:
            raise ValueError(ident + ' pair failed: ' + log.read_text()[-1600:])
        receipt = json.loads(output.read_text())
        if (receipt.get('comparison_id') != ident or
                receipt.get('case_ids') != pair['case_ids'] or
                receipt.get('diagnostic_audit_passed') is not True or
                receipt.get('diagnostic_fixture') is not True or
                receipt.get('physical_acceptance_claimed') is not False):
            raise ValueError(ident + ' comparison result differs')
        results.append({'comparison_id': ident, 'case_ids': pair['case_ids'],
                        'audit': {'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
                                  'command': ' '.join(command),
                                  'test_exit_code': 0, 'test_log': log.name,
                                  'test_log_sha256': sha(log),
                                  'result_sha256': sha(output),
                                  'diagnostic_fixture': True,
                                  'physical_acceptance_claimed': False}})
    result = {'format': 'worker-comparison-audits',
              'assignment_id': HERE.name, 'comparisons': results}
    (HERE / 'comparison-audits.json').write_text(json.dumps(result, indent=2) + '\n')
    return len(results)


if __name__ == '__main__':
    print(prove())
