"""Independent exact-pair audit of sealed original Native histories.

The output describes source and isolation checks; it never decides statutory
authorization or substitutes for original pixel and physical review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_audit import audit_history


VARIABLES = {'approach', 'route_class', 'vehicle_class', 'sign_permits_shoulder',
             'emergency_required', 'subsection3_authorized'}
FIXED_SOURCES = ('map_sha256', 'lane_marking_source_sha256',
                 'legal_controlled_access_source_sha256',
                 'public_highway_boundary_source_sha256', 'camera_plan_sha256',
                 'direction_source_sha256', 'sign_source_sha256',
                 'emergency_record_source_sha256',
                 'subsection3_authorization_source_sha256')


def audit(plan_path: Path, comparison_id: str, history_paths: list[Path],
          history_sha256: list[str], map_sha256: str) -> dict:
    plan = json.loads(Path(plan_path).read_text())
    matches = [item for item in plan['comparisons'] if item['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('exact comparison missing or duplicated')
    pair = matches[0]
    if len(pair['case_ids']) != 2 or len(history_paths) != 2 or len(history_sha256) != 2:
        raise ValueError('exact comparison needs two original histories')
    declared = set(pair['deliberate_differences'])
    if not declared or not declared <= VARIABLES:
        raise ValueError('unknown deliberate comparison variable')
    audited = []
    for path, digest, case_id in zip(history_paths, history_sha256, pair['case_ids']):
        record = audit_history(Path(path), digest, case_id.split('__')[-1], map_sha256)
        record['case_id'] = case_id
        audited.append(record)
    left, right = audited
    for key in FIXED_SOURCES:
        if left['fixed'][key] != right['fixed'][key]:
            raise ValueError('fixed source changed: ' + key)
    if left['first_original_frame'] != right['first_original_frame']:
        raise ValueError('original frame windows differ')
    with Path(history_paths[0]).open() as source:
        lrow = json.loads(source.readline())
    with Path(history_paths[1]).open() as source:
        rrow = json.loads(source.readline())
    for key in VARIABLES:
        lval, rval = left['fixed'].get(key), right['fixed'].get(key)
        if key in ('sign_permits_shoulder', 'emergency_required', 'subsection3_authorized'):
            # These are original frame records outside the source identity fields.
            lval, rval = lrow[key], rrow[key]
        if key in declared and lval == rval:
            raise ValueError('deliberate difference absent: ' + key)
        if key not in declared and lval != rval:
            raise ValueError('undeclared comparison change: ' + key)
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': pair['case_ids'], 'changed': sorted(declared),
            'original_history_sha256': history_sha256,
            'source_isolation_passed': True, 'physical_acceptance': False,
            'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-history', type=Path, required=True)
    parser.add_argument('--right-history', type=Path, required=True)
    parser.add_argument('--left-sha256', required=True)
    parser.add_argument('--right-sha256', required=True)
    parser.add_argument('--map-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.plan, args.comparison,
                           [args.left_history, args.right_history],
                           [args.left_sha256, args.right_sha256], args.map_sha256)))


if __name__ == '__main__':
    main()
