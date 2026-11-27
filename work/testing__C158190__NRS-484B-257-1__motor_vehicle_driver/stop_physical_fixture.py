"""Exercise the selected engineering crossing probe on labeled synthetic rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stop_physical_completion import assess
from stop_sign_branch import ASSIGNMENT, CASES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.case not in CASES:
        raise ValueError('exact selected stop case required')
    context_path = args.sources/'context.json'
    rows_path = args.sources/'original-trace.jsonl'
    site = json.loads(context_path.read_text())
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if len(rows) != 9 or site.get('case_id') != args.case or site.get('source_kind') != 'synthetic_diagnostic_fixture':
        raise ValueError('labeled synthetic stop fixture missing')
    for i, row in enumerate(rows):
        row['ego_within_intersection'] = args.kind == 'complete_motion' and 3 <= i <= 6
    if args.kind == 'missing_evidence':
        rows[4].pop('ego_within_intersection')
    probe = assess(rows, site, expected_frames=9)
    expected = {'complete_motion':'met', 'incomplete_motion':'not_met', 'missing_evidence':'unverified'}[args.kind]
    if probe['status'] != expected:
        raise ValueError('synthetic crossing outcome differs')
    result = {'case_id': args.case, 'kind': args.kind,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'maneuver_completed': probe['status'] == 'met',
              'physical_checks': {'maneuver': {
                  'status': probe['status'], 'method': 'source-joined frame occupancy, entry and exit',
                  'sources': [{'path': str(context_path), 'sha256': sha(context_path)},
                              {'path': str(rows_path), 'sha256': sha(rows_path)}]}},
              'realized_observables': probe if probe['status'] == 'met' else {},
              'physical_completion_claimed': False, 'legal_judgment': None}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind, 'status': probe['status']}, sort_keys=True))


if __name__ == '__main__':
    main()
