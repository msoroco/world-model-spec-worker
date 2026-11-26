"""Independent source-bound truck comparison audit; no legal verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from truck_following import audit_comparison

FIELDS = {
    '500ft_space_below_at_above': (
        ('subject_width_min_m', 'lead_width_min_m', 'same_direction_available_lane_count_min',
         'entered_gap_distinct_vehicle_count', 'subject_pass_geometry_verified',
         'surrounding_vehicle_count_max'), 'steady_gap_min_m'),
    'passing_permission': (
        ('steady_gap_min_m', 'subject_width_min_m', 'lead_width_min_m',
         'same_direction_available_lane_count_min', 'entered_gap_distinct_vehicle_count',
         'surrounding_vehicle_count_max'), 'subject_pass_geometry_verified'),
    'entering_vehicle': (
        ('steady_gap_min_m', 'subject_width_min_m', 'lead_width_min_m',
         'same_direction_available_lane_count_min', 'subject_pass_geometry_verified'),
        'entered_gap_distinct_vehicle_count'),
    'multilane_exception': (
        ('steady_gap_min_m', 'subject_width_min_m', 'lead_width_min_m',
         'entered_gap_distinct_vehicle_count', 'subject_pass_geometry_verified',
         'surrounding_vehicle_count_max'), 'same_direction_available_lane_count_min'),
    'lead_width_qualification': (
        ('steady_gap_min_m', 'subject_width_min_m', 'same_direction_available_lane_count_min',
         'entered_gap_distinct_vehicle_count', 'subject_pass_geometry_verified',
         'surrounding_vehicle_count_max'), 'lead_width_min_m'),
    'subject_width_qualification': (
        ('steady_gap_min_m', 'lead_width_min_m', 'same_direction_available_lane_count_min',
         'entered_gap_distinct_vehicle_count', 'subject_pass_geometry_verified',
         'surrounding_vehicle_count_max'), 'subject_width_min_m'),
    'conditions_permit': (
        ('steady_gap_min_m', 'subject_width_min_m', 'lead_width_min_m',
         'same_direction_available_lane_count_min', 'entered_gap_distinct_vehicle_count',
         'subject_pass_geometry_verified'), 'surrounding_vehicle_count_max'),
}


def audit(comparison_id: str, reports: list[dict]) -> dict:
    if comparison_id not in FIELDS or len(reports) < 2:
        raise ValueError('unknown or incomplete exact comparison')
    fixed, varied = FIELDS[comparison_id]
    results = [audit_comparison(reports[0], other, fixed_fields=fixed, varied_field=varied)
               for other in reports[1:]]
    return {'format': 'c149752-source-bound-comparison-audit',
            'comparison_id': comparison_id, 'checks': results,
            'physical_acceptance_claimed': False, 'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--report', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(Path(path).read_text(encoding='utf-8')) for path in args.report]
    if args.output.exists():
        raise ValueError('comparison audit output already exists')
    args.output.write_text(json.dumps(audit(args.comparison, reports), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
