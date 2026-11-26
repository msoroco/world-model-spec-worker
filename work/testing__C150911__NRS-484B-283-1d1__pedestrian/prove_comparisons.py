"""Run three exact saved diagnostic WALK comparisons and source negatives."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import compare


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    results = []
    for row in plan['comparisons']:
        cid = row['comparison_id']
        attempts = [REPO / '.runtime-work/c150911-owner/compat-selected' /
            case_id.split('__')[-1] / 'primary' for case_id in row['case_ids']]
        out = REPO / '.runtime-work/c150911-owner/comparisons' / (cid + '.json')
        if out.exists():
            out.unlink()
        command = [sys.executable, str(ROOT / 'comparison_audit.py'),
            '--comparison', cid, '--first-attempt', str(attempts[0]),
            '--second-attempt', str(attempts[1]), '--output', str(out),
            '--diagnostic-fixture']
        completed = subprocess.run(command, capture_output=True, text=True, env=os.environ)
        log = ROOT / ('comparison-' + cid + '.log')
        log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
        if completed.returncode:
            raise ValueError('saved comparison failed: ' + cid + ': ' + log.read_text()[-500:])
        receipt = ROOT / ('comparison-' + cid + '.json')
        receipt.write_bytes(out.read_bytes())
        negative = REPO / '.runtime-work/c150911-owner/comparison-negative' / cid
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(attempts[1], negative, copy_function=os.link)
        (negative / 'original-walk-observations.json').unlink()
        try:
            compare(cid, attempts[0], negative, diagnostic=True)
        except ValueError as error:
            source_error = str(error)
            if 'Missing required source: original-walk-observations.json' not in source_error:
                raise
        else:
            raise ValueError('missing original WALK source accepted')
        negative_log = ROOT / ('comparison-negative-' + cid + '.log')
        negative_log.write_text(source_error + '\n')
        results.append({'comparison_id': cid, 'case_ids': row['case_ids'],
            'exit_code': 0, 'command': ' '.join(command),
            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
            'receipt': str(receipt.relative_to(ROOT)), 'receipt_sha256': sha(receipt),
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': sha(negative_log)})
        print(cid, 'passed', flush=True)
    (ROOT / 'cpu-comparison-proofs.json').write_text(
        json.dumps(results, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
