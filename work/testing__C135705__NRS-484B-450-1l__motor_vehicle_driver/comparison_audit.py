"""Independent original-only highway-side relation, activity and exception comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parking import CASES

AID = 'testing__C135705__NRS-484B-450-1l__motor_vehicle_driver'
PAIRS = {
    'side_relationship': ('side_park', 'behind_park'),
    'activity_stop': ('side_park', 'side_stop'),
    'activity_stand': ('side_park', 'side_stand'),
    'traffic_conflict_exception': ('side_stop', 'side_conflict'),
    'law_compliance_exception': ('side_stop', 'side_law'),
    'police_direction_exception': ('side_stop', 'side_police'),
    'device_direction_exception': ('side_stop', 'side_device')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown parking comparison')
    ids = [AID + '__' + suffix for suffix in suffixes]
    pair = [reports.get(case_id) for case_id in ids]
    for case_id, report in zip(ids, pair):
        require(isinstance(report, dict) and report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id') == case_id and report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') == 'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = [report['comparison_record'] for report in pair]
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(a.get(key) and a[key] == b.get(key),
                'changed fixed original condition: ' + key)
    left, right = [next(case for case in CASES if case.case_id == suffix) for suffix in suffixes]
    for record, case in ((a, left), (b, right)):
        require((record.get('requested_endpoint'), record.get('activity'),
                 record.get('exception'), record.get('edge_vehicle_status')) ==
                (case.endpoint, case.activity, case.exception_probe, 'parked'),
                'original parking case variables differ')
    x, y = a['measurement'], b['measurement']
    require(x.get('frame_count') == y.get('frame_count') == 900,
            'original parking measurement frame count differs')
    for row in (x, y):
        require(row.get('edge_stationary_observed') is True and
                row.get('ego_halt_observed') is True and
                type(row.get('terminal_roadward_lateral_difference_m')) in (int, float) and
                type(row.get('terminal_along_edge_difference_m')) in (int, float),
                'original two-vehicle halt measurement absent')
    if comparison_id == 'side_relationship':
        require(left.endpoint != right.endpoint and
                x['terminal_roadward_lateral_difference_m'] > .5 and
                abs(y['terminal_roadward_lateral_difference_m']) < .5 and
                abs(y['terminal_along_edge_difference_m']) > 5,
                'original highway-side versus behind relation absent')
    elif comparison_id in ('activity_stop', 'activity_stand'):
        require(left.endpoint == right.endpoint == 'highway_side' and
                left.exception_probe == right.exception_probe is None and
                left.activity != right.activity,
                'isolated ordinary halt activity contrast absent')
    else:
        require(left.endpoint == right.endpoint == 'highway_side' and
                left.activity == right.activity == 'stop' and
                left.exception_probe is None and right.exception_probe is not None and
                y.get('exception_source_sha256'),
                'isolated exception source contrast absent')
    return {'format': 'c135705-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'terminal_lateral_differences_m': [
                x['terminal_roadward_lateral_difference_m'],
                y['terminal_roadward_lateral_difference_m']],
            'terminal_longitudinal_differences_m': [
                x['terminal_along_edge_difference_m'],
                y['terminal_along_edge_difference_m']],
            'physical_comparison_passed': True, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {case_id: json.loads(Path(path).read_text()) for case_id, path in paths.items()}
    result = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
