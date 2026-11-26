"""Independent saved source and comparison audit; never grants physical acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from analysis import build, compare
from overtake import require


def audit_delivery(attempt, report_path):
    expected, _ = build(attempt)
    report = json.loads(Path(report_path).read_text())
    require(report == expected, 'saved original analysis differs from source readback')
    measured = report['measurements']['cycle_motor_pass']['value']
    require(measured['frame_count'] == 900 and
            measured['initial_relative_station_m'] < 0,
            'original approach history incomplete')
    require(measured['minimum_surface_clearance_m'] >= 0,
            'original body surface overlap')
    require(report['physical_acceptance_claimed'] is False and
            report['legal_verdict_claimed'] is False,
            'software audit cannot accept physical or legal outcome')
    return {'format': 'worker-c229023-delivery-source-audit',
            'case_id': report['case_id'],
            'attempt_sources_sha256': hashlib.sha256(
                (Path(attempt) / 'original-sources.json').read_bytes()).hexdigest(),
            'analysis_report_sha256': hashlib.sha256(
                Path(report_path).read_bytes()).hexdigest(),
            'original_frame_count': 900,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def audit_comparison(plan_path, comparison_id, left_path, right_path):
    plan = json.loads(Path(plan_path).read_text())
    rows = [item for item in plan['comparisons'] if
            item['comparison_id'] == comparison_id]
    require(len(rows) == 1, 'unknown exact comparison')
    left = json.loads(Path(left_path).read_text())
    right = json.loads(Path(right_path).read_text())
    return compare(left, right, rows[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--comparison')
    parser.add_argument('--left', type=Path)
    parser.add_argument('--right', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.comparison:
        require(args.plan and args.left and args.right,
                'comparison source reports required')
        result = audit_comparison(args.plan, args.comparison,
                                  args.left, args.right)
    else:
        require(args.attempt and args.report, 'original attempt and report required')
        result = audit_delivery(args.attempt, args.report)
    require(not args.output.exists(), 'retain prior audit')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
