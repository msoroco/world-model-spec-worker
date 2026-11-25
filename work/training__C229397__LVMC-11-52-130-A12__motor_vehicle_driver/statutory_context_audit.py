"""Independent source binding for the marked-crosswalk qualifier and exceptions.

This audit reports source review findings. It does not decide whether the
statutory exception applies or whether a stop, stand, or park is lawful.
"""
import argparse
import hashlib
import json
from pathlib import Path

from source_review import FIELDS, join


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / 'config.json').read_text())
    if config.get('case_id') != case_id or config.get('selected_case_id') != case_id:
        raise ValueError('statutory context case identity differs')
    inventory_path = attempt / 'crosswalk-inventory.json'
    inventory = json.loads(inventory_path.read_text())
    if inventory.get('source_kind') != 'native_saved_sample':
        raise ValueError('statutory context requires original Native inventory')
    joined, review_sha, findings = join(attempt, inventory)
    if set(findings) != set(FIELDS):
        raise ValueError('statutory context findings incomplete')
    return {
        'format': 'c229397-statutory-context-audit-v1',
        'case_id': case_id,
        'inventory_sha256': sha(inventory_path),
        'review_sha256': review_sha,
        'source_bindings': {field: joined[field] for field in FIELDS},
        'findings': findings,
        'exception_review': {
            'traffic_conflict': findings['traffic_conflict_review_source_id'],
            'law_compliance': findings['law_compliance_review_source_id'],
            'police_or_device_directions': findings['directions_review_source_id'],
        },
        'marked_crosswalk_established_by_review': findings['marked_crosswalk_source_id'] == 'present',
        'legal_verdict': None,
        'physical_acceptance_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
