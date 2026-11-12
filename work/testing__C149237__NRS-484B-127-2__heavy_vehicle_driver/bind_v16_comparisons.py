"""Reprove and bind all four independent saved-source comparisons after v16 bundles."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPECS = (
    ('gap_500ft_boundary', 'gap-boundary', 'gap_comparison_audit.py', 'prove_gap_comparison.py'),
    ('qualifying_vehicle_width', 'width-boundary', 'width_comparison_audit.py', 'prove_width_comparison.py'),
    ('two_lanes_exception', 'lane-exception', 'lane_comparison_audit.py', 'prove_lane_comparison.py'),
    ('overtaking_exception', 'overtaking-exception', 'overtaking_comparison_audit.py', 'prove_overtaking_comparison.py'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = HERE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    by_id = {item['comparison_id']: item for item in plan['comparisons']}
    for comparison_id, stem, audit_script, proof_script in SPECS:
        proof_log = HERE/f'{stem}-proof-v16.log'
        with proof_log.open('w') as stream:
            result = subprocess.run(['.venv-cpu/bin/python', str(HERE/proof_script)],
                                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError('Comparison proof failed: '+str(proof_log))
        output = json.loads(proof_log.read_text())
        positive = output['positive']
        if not positive['passed'] or len(positive['case_ids']) != len(by_id[comparison_id]['case_ids']):
            raise ValueError('Comparison coverage changed: '+comparison_id)
        receipt = HERE/f'{stem}-comparison-v16.json'
        receipt.write_text(json.dumps(positive, indent=2)+'\n')
        positive_log = HERE/f'{stem}-comparison-v16.log'
        positive_log.write_text(json.dumps({'passed': True, 'case_count': len(positive['case_ids'])}, indent=2)+'\n')
        item = by_id[comparison_id]
        item['case_ids'] = positive['case_ids']
        item['cpu_audit'] = {'script': audit_script, 'script_sha256': sha(HERE/audit_script),
                             'receipt': receipt.name, 'receipt_sha256': sha(receipt),
                             'positive_log': positive_log.name, 'positive_log_sha256': sha(positive_log),
                             'negative_log': proof_log.name, 'negative_log_sha256': sha(proof_log),
                             'scope': 'nine-frame synthetic saved-source comparison; physical/legal findings unverified'}
        print('passed', comparison_id, flush=True)
    plan_path.write_text(json.dumps(plan, indent=2)+'\n')


if __name__ == '__main__':
    main()
