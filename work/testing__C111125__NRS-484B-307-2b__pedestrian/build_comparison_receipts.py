"""Publish exact diagnostic pair audits with a source-change rejection."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c111125-owner/comparison'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(value.rstrip() + '\n')


def main():
    if not os.getenv('SCENARIO_PIPELINE_OUTPUT_ROOT') or not os.getenv('TMPDIR'):
        raise ValueError('runtime output and temporary roots must be exported')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    receipts = []
    for row in plan['comparisons']:
        comparison_id = row['comparison_id']
        outcomes = {}
        for mode in ('positive', 'negative'):
            args = [sys.executable, str(ROOT / 'prove_comparison.py'),
                    '--comparison', comparison_id, '--scratch', str(SCRATCH),
                    '--mode', mode]
            done = subprocess.run(args, cwd=REPO, text=True, capture_output=True,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log = ROOT / 'comparisons' / (comparison_id + '-' + mode + '.log')
            log.parent.mkdir(exist_ok=True)
            write(log, done.stdout + done.stderr)
            if mode == 'positive':
                if done.returncode != 0:
                    raise RuntimeError(f'{comparison_id} positive failed: {log}')
                proof = json.loads(done.stdout)
                if proof.get('passed') is not True:
                    raise RuntimeError('positive result did not pass')
                outcomes['positive'] = proof
            else:
                if done.returncode == 0 or 'fixed condition differs: signal_source_sha256' not in done.stderr:
                    raise RuntimeError(f'{comparison_id} source-change negative failed: {log}')
                outcomes['negative_rejected'] = True
            outcomes[mode + '_log'] = str(log.relative_to(ROOT))
            outcomes[mode + '_log_sha256'] = sha(log)
        receipts.append({'comparison_id': comparison_id,
                         'case_ids': row['case_ids'],
                         'source_scope': '900-frame synthetic diagnostic extension',
                         'audit_source': 'comparison_audit.py',
                         'audit_source_sha256': sha(ROOT / 'comparison_audit.py'),
                         'proof_source_sha256': sha(ROOT / 'prove_comparison.py'),
                         **outcomes})
    output = ROOT / 'comparison-receipts.draft.json'
    write(output, json.dumps({'assignment_id': ROOT.name, 'status': 'diagnostic_cpu_only',
                              'comparisons': receipts}, indent=2))
    print(json.dumps({'comparisons': len(receipts), 'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
