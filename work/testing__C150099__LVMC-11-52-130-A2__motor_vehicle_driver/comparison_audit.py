"""Independent original-history comparison; no legal outcome is assigned."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_audit import audit_planned_case

FIXED = (
    'map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
    'posting_authority_sha256', 'posted_extent_sha256', 'sign_identity_sha256',
    'sign_appearance_sha256', 'curb_geometry_sha256', 'property_source_sha256',
    'route_sha256', 'weather_sha256', 'camera_plan_sha256',
)


def audit_pair(plan: dict, comparison_id: str, left: dict, right: dict) -> dict:
    """Read two sealed attempts and enforce the planned single difference."""
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('exact comparison missing')
    comparison = matches[0]
    if [left.get('case_id'), right.get('case_id')] != comparison['case_ids']:
        raise ValueError('comparison case order changed')
    if len(comparison['deliberate_differences']) != 1:
        raise ValueError('comparison must declare one difference')
    changed = comparison['deliberate_differences'][0]
    if changed not in ('attended', 'activity', 'target_region', 'exception'):
        raise ValueError('comparison difference unsupported')
    reports = []
    for source in (left, right):
        reports.append(audit_planned_case(
            Path(source['history_path']), source['history_sha256'],
            source['case_id'], source['site_sha256']))
    a, b = reports
    for key in FIXED:
        if not a['fixed_sources'].get(key) or a['fixed_sources'][key] != b['fixed_sources'].get(key):
            raise ValueError('fixed original source changed: ' + key)
    for key in ('attended', 'property_kind', 'activity', 'target_region', 'exception'):
        if key == changed:
            if a['observed'][key] == b['observed'][key]:
                raise ValueError('planned original difference absent: ' + key)
        elif a['observed'][key] != b['observed'][key]:
            raise ValueError('undeclared original difference: ' + key)
    return {
        'format': 'worker-original-comparison-audit',
        'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
        'original_history_sha256': [a['original_history_sha256'],
                                    b['original_history_sha256']],
        'fixed_source_keys': list(FIXED), 'deliberate_difference': changed,
        'observed': [a['observed'], b['observed']],
        'legal_judgment': None, 'physical_visibility_verified': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())
    print(json.dumps(audit_pair(plan, args.comparison, left, right), sort_keys=True))


if __name__ == '__main__':
    main()
