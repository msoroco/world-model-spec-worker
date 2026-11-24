"""Check one exact red-curb case against independently saved CPU diagnostics.

The positive result proves the audit template and synthetic source binding. It
does not assert original Native motion, visible pixels, physical completion, or
a legal outcome. The negative path rejects absent original source explicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(case, missing_source=False):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    selected = {entry['case_id']: entry for entry in manifest['cases']}
    require(len(selected) == 30 and case in selected,
            'Exact selected red-curb case missing')
    source_path = HERE / 'current-all-selected-delivery-diagnostic.json'
    source = json.loads(source_path.read_text())
    require(source['passed'] is True and
            source['manifest_sha256'] == sha(manifest_path) and
            source['selected_cases'] == len(selected) and
            source['source_kind'] == 'synthetic_native_sample' and
            source['original_native_observed'] is False and
            source['physical_acceptance_claimed'] is False and
            source['legal_acceptance_claimed'] is False,
            'Selected diagnostic source audit stale or overclaimed')
    exception_path = HERE / 'current-selected-exception-delivery-diagnostic.json'
    exception = json.loads(exception_path.read_text())
    require(sha(exception_path) == source['exception_audit_receipt_sha256'] and
            sha(HERE / 'audit-current-selected-exception-delivery.py') ==
            source['exception_audit_script_sha256'] and exception['passed'] is True,
            'Exception saved source audit changed')
    rows = {row['case_id']: row for row in source['ordinary_cases'] +
            exception['rows']}
    require(set(rows) == set(selected) and rows[case]['frames'] >= 2 and
            len(rows[case].get('source_decode_receipts', [1, 2, 3, 4])) == 4,
            'Exact diagnostic source or camera decode audit missing')
    if missing_source:
        raise ValueError('Missing independent original Native and physical acceptance source: ' + case)
    return {'format': 'c150142-case-delivery-cpu-preparation-v1',
            'case_id': case, 'passed': True, 'checks': list(CHECKS),
            'manifest_sha256': sha(manifest_path),
            'source_audit_sha256': sha(source_path),
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--missing-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.missing_source), sort_keys=True))
