"""Independent original-history comparison; no legal outcome is assigned."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from saved_audit import audit_planned_case

FIXED = (
    'map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
    'posting_authority_sha256', 'posted_extent_sha256', 'sign_identity_sha256',
    'sign_appearance_sha256', 'curb_geometry_sha256', 'property_source_sha256',
    'route_sha256', 'weather_sha256', 'camera_plan_sha256',
)


def audit_sweep(plan: dict, comparison_id: str, sources: list[dict]) -> dict:
    """Compare sealed original histories for a three-point source-review grid.

    The last 100 original frames form the stable measurement window. The
    requested engineering setpoints are never substituted for observations.
    """
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('exact sweep comparison missing')
    comparison = matches[0]
    axis = comparison['deliberate_differences']
    if axis not in (['conflict_gap_m'], ['posted_offset_m']):
        raise ValueError('unsupported sweep comparison axis')
    if len(sources) != 3 or [row.get('case_id') for row in sources] != comparison['case_ids']:
        raise ValueError('sweep comparison case order changed')
    reports = []
    medians = []
    first_sources = None
    first_observed = None
    for source in sources:
        report = audit_planned_case(Path(source['history_path']), source['history_sha256'],
                                    source['case_id'], source['site_sha256'])
        fixed = report['fixed_sources']
        if first_sources is None:
            first_sources = fixed
            first_observed = report['observed']
        elif any(not fixed.get(key) or fixed[key] != first_sources.get(key)
                 for key in ('site_sha256', *FIXED)):
            raise ValueError('sweep fixed original source changed')
        if any(report['observed'][key] != first_observed[key]
               for key in ('attended', 'property_kind', 'activity', 'target_region',
                           'exception', 'hold_frame_count')):
            raise ValueError('sweep undeclared original difference')
        measured = report['sweep_measurement']
        key = 'measured_gap_m' if axis == ['conflict_gap_m'] else 'measured_offset_m'
        values = measured.get(key)
        if not isinstance(values, list) or len(values) != report['frame_count']:
            raise ValueError('sweep original measurement absent')
        medians.append(statistics.median(values[-100:]))
        reports.append(report)
    if len(set(medians)) != 3:
        raise ValueError('sweep original contrast absent')
    return {'format': 'worker-original-sweep-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'original_history_sha256': [r['original_history_sha256'] for r in reports],
            'fixed_source_keys': ['site_sha256', *FIXED], 'deliberate_difference': axis[0],
            'observed_final_window_median_m': medians,
            'legal_judgment': None, 'physical_visibility_verified': False}


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
    parser.add_argument('--left', type=Path)
    parser.add_argument('--right', type=Path)
    parser.add_argument('--sources', type=Path, nargs=3)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if args.sources:
        if args.left or args.right:
            parser.error('--sources cannot be combined with --left or --right')
        sources = [json.loads(path.read_text()) for path in args.sources]
        result = audit_sweep(plan, args.comparison, sources)
    else:
        if not args.left or not args.right:
            parser.error('pair audit requires --left and --right')
        result = audit_pair(plan, args.comparison,
                            json.loads(args.left.read_text()), json.loads(args.right.read_text()))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
