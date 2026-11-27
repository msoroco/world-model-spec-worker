"""Independent exact-case right-side comparison audit."""

import argparse
import json
from pathlib import Path

from rightside import need


VARIABLES = ('cycle_kind', 'requested_lateral_target_m', 'right_impediment',
             'narrow_lane', 'traffic_speed_context', 'left_turn_preparation',
             'target_motion')


def value(report):
    need(report.get('format') == 'worker-analysis-report' and
         report.get('analysis_complete') is True and
         report.get('physical_acceptance_claimed') is False and
         report.get('legal_verdict_claimed') is False,
         'source-bound analysis report required')
    measurements = report.get('measurements')
    need(isinstance(measurements, dict) and measurements,
         'source-bound right-side measurement missing')
    first = next(iter(measurements.values()))
    need(first.get('method') == 'measure_case' and first.get('sources') and
         isinstance(first.get('value'), dict),
         'source-bound right-side measurement missing')
    need(all(item.get('value') == first['value'] and item.get('sources') == first['sources']
             for item in measurements.values()),
         'requirement measurements disagree')
    return first['value']


def audit(plan, comparison_id, left, right):
    rows = [item for item in plan['comparisons']
            if item['comparison_id'] == comparison_id]
    need(len(rows) == 1, 'unknown exact comparison')
    comparison = rows[0]
    need({left.get('case_id'), right.get('case_id')} == set(comparison['case_ids']) and
         left.get('case_id') != right.get('case_id'),
         'two exact comparison cases required')
    a, b = value(left), value(right)
    need(a['frame_count'] == b['frame_count'] == 900 and
         a['road_geometry_source_sha256'] == b['road_geometry_source_sha256'] and
         a['lawful_speed_basis_source_sha256'] == b['lawful_speed_basis_source_sha256'],
         'fixed original roadway, speed basis or duration differs')
    differences = {key for key in VARIABLES if a[key] != b[key]}
    declared = set(comparison['deliberate_differences'])
    need(differences == declared, 'comparison changed undeclared condition or failed to vary target')
    need(a['initial_relative_station_m'] < 0 and b['initial_relative_station_m'] < 0 and
         a['terminal_relative_station_m'] > 0 and b['terminal_relative_station_m'] > 0 and
         a['minimum_surface_clearance_m'] >= 0 and b['minimum_surface_clearance_m'] >= 0,
         'original passing phases or body clearance missing')
    return {'format': 'worker-right-side-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions': comparison['fixed_conditions'],
            'deliberate_differences': comparison['deliberate_differences'],
            'measured': [a, b], 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'retain prior comparison audit')
    plan = json.loads(args.plan.read_text())
    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())
    args.output.write_text(json.dumps(audit(plan, args.comparison, left, right),
                                      indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
