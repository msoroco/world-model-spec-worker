"""Run five independent diagnostic comparison audits and bind their receipts."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from comparison_audit import CHANGED


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for comparison_id in CHANGED:
        receipt = HERE / f'comparison-{comparison_id}-proof.json'
        log = HERE / f'comparison-{comparison_id}-positive.log'
        command = [sys.executable, str(HERE / 'comparison_audit.py'), '--comparison',
                   comparison_id, '--output', str(receipt)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError(f'{comparison_id}: {log.read_text()}')
        entries.append({'comparison_id': comparison_id, 'command': ' '.join(command),
                        'exit_code': result.returncode, 'log': log.name,
                        'log_sha256': sha(log), 'receipt': receipt.name,
                        'receipt_sha256': sha(receipt)})
        print(comparison_id, 'passed')
    (HERE / 'comparison-proof-index.json').write_text(json.dumps({
        'format': 'worker-turn-comparison-proof-index',
        'assignment_id': HERE.name, 'script': 'comparison_audit.py',
        'script_sha256': sha(HERE / 'comparison_audit.py'), 'comparisons': entries,
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
