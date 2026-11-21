"""Audit all exact primary diagnostic sources and five controlled pairs."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit
from delivery_comparison_audit import compare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='update134')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    digest = sha(MANIFEST)
    output = HERE / (args.label + '-selected-primary-audits')
    output.mkdir(parents=True, exist_ok=True)
    attempts, audit_paths, case_rows = {}, {}, []
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case[len(HERE.name) + 2:]
        proof_path = HERE / (args.label + '-' + short + '-primary-proof.json')
        proof = json.loads(proof_path.read_text())
        if proof['manifest_sha256'] != digest or proof['case_id'] != case:
            raise ValueError('Current primary chain proof missing')
        base = ROOT / '.runtime-work' / ('c183370-' + args.label + '-' + short + '-primary')
        attempt = Path(str(base) + '-source')
        processing = Path(str(base) + '-saved/v0001/processing.json')
        value = audit(MANIFEST, case, 'primary', attempt, processing, True)
        if value['accepted'] is not False or value['diagnostic_only'] is not True:
            raise ValueError('Diagnostic audit asserted original acceptance')
        receipt = output / (short + '.json')
        if receipt.exists():
            if json.loads(receipt.read_text()) != value:
                raise ValueError('Previous current primary audit differs')
        else:
            receipt.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
        attempts[case], audit_paths[case] = attempt, receipt
        case_rows.append({'case_id': case, 'chain_sha256': sha(proof_path),
                          'audit_sha256': sha(receipt), 'accepted': False})
    comparisons = []
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for row in plan['comparisons']:
        case_a, case_b = row['case_ids']
        value = compare(row['comparison_id'], audit_paths[case_a], audit_paths[case_b],
                        attempts[case_a], attempts[case_b], True, MANIFEST)
        if value['accepted'] is not False:
            raise ValueError('Comparison asserted original acceptance')
        receipt = output / (row['comparison_id'].split('__comparison_')[-1] + '-comparison.json')
        if receipt.exists():
            raise ValueError('Retain previous current comparison audit')
        receipt.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
        comparisons.append({'comparison_id': row['comparison_id'],
                            'sha256': sha(receipt), 'accepted': False})
    summary = {'format': 'c183370-current-selected-primary-diagnostic-matrix-v1',
               'manifest_sha256': digest, 'primary_count': len(case_rows),
               'comparison_count': len(comparisons), 'original_native_observed': False,
               'physical_or_legal_acceptance_claimed': False,
               'cases': case_rows, 'comparisons': comparisons}
    path = HERE / (args.label + '-selected-primary-diagnostic-matrix.json')
    if path.exists():
        raise ValueError('Retain previous primary diagnostic matrix')
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'primary_count': len(case_rows),
                      'comparison_count': len(comparisons),
                      'matrix_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
