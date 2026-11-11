"""Join diagnostic comparison proofs to the current saved-only case receipts.

This checks software provenance and comparison isolation, not physical outcomes.
"""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(folder=HERE):
    folder = Path(folder)
    manifest_path = folder / 'execution-manifest.json'
    manifest_hash = sha(manifest_path)
    manifest = read(manifest_path)
    manifest_cases = {row['case_id']: row for row in manifest['cases']}
    case_ids = set(manifest_cases)
    require(len(case_ids) == len(manifest['cases']), 'Duplicate manifest case')
    saved_index = read(folder / 'aggregate-saved/index.json')
    require(saved_index['manifest_sha256'] == manifest_hash, 'Stale saved manifest hash')
    require(saved_index['assignment_id'] == folder.name, 'Wrong saved assignment')
    saved = {}
    for row in saved_index['cases']:
        case_id = row['case_id']
        require(case_id not in saved, 'Duplicate saved case')
        receipt_path = folder / row['receipt']
        log_path = folder / row['log']
        require(sha(receipt_path) == row['sha256'] and sha(log_path) == row['log_sha256'],
                'Changed saved receipt or log: ' + case_id)
        receipt = read(receipt_path)
        require(receipt['case_id'] == case_id and receipt['manifest_sha256'] == manifest_hash
                and receipt['construction_sha256'] == manifest_cases[case_id]['construction_sha256']
                and receipt['passed'] is True and receipt['originals_preserved'] is True
                and receipt['missing_evidence'] is False, 'Invalid saved processing: ' + case_id)
        saved[case_id] = receipt
    require(set(saved) == case_ids, 'Saved processing omits a selected case')

    plan = read(folder / 'case-plan.json')
    expected = {row['comparison_id']: set(row['case_ids']) for row in plan['comparisons']}
    comparison_index = read(folder / 'comparison-proof-index.json')
    require(comparison_index['assignment_id'] == folder.name, 'Wrong comparison assignment')
    comparison_path = folder / comparison_index['script']
    require(sha(comparison_path) == comparison_index['script_sha256'], 'Changed comparison auditor')
    compared = {}
    for row in comparison_index['comparisons']:
        cid = row['comparison_id']
        require(cid not in compared, 'Duplicate comparison')
        path = folder / row['receipt']
        require(sha(path) == row['receipt_sha256']
                and sha(folder / row['log']) == row['log_sha256']
                and row['exit_code'] == 0, 'Changed or failed comparison proof: ' + cid)
        proof = read(path)
        members = proof['case_ids']
        require(proof['comparison_id'] == cid and set(members) == expected.get(cid)
                and len(members) == len(set(members)), 'Comparison cases changed: ' + cid)
        fixed = proof['fixed_source_sha256']
        differences = proof['declared_difference_sources']
        require(fixed and differences and not set(fixed) & set(differences),
                'Missing or overlapping source declarations: ' + cid)
        for source, digest in fixed.items():
            require(all(saved[case]['original_source_hashes'].get(source) == digest for case in members),
                    'Saved fixed source changed: ' + cid + '/' + source)
        for source in differences:
            values = [saved[case]['original_source_hashes'].get(source) for case in members]
            require(any(value is not None for value in values) and len(set(values)) > 1,
                    'Saved difference absent: ' + cid + '/' + source)
        compared[cid] = {'case_ids': members, 'fixed_sources': fixed,
                         'difference_sources': differences,
                         'diagnostic_proof_sha256': row['receipt_sha256']}
    require(set(compared) == set(expected), 'Missing selected comparison')
    return {'format': 'worker-turn-saved-comparison-audit',
            'assignment_id': folder.name, 'manifest_sha256': manifest_hash,
            'saved_index_sha256': sha(folder / 'aggregate-saved/index.json'),
            'comparison_index_sha256': sha(folder / 'comparison-proof-index.json'),
            'comparisons': compared, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('saved_comparison_audit_passed', len(result['comparisons']))
