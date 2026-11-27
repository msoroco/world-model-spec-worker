"""Independent original-only route and designation contrasts for NRS 484B.110."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from zone_motion import CASES

AID = 'testing__C412974__NRS-484B-110__motor_vehicle_driver'
PAIRS = {
    'through_vs_beside': ('through_zone', 'beside_zone', 'route'),
    'through_vs_within': ('through_zone', 'within_zone', 'route'),
    'through_vs_unverified': ('through_zone', 'through_unverified_designation', 'designation'),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def audit_pair(comparison_id: str, reports: dict) -> dict:
    selection = PAIRS.get(comparison_id)
    require(selection is not None, 'unknown safety-zone comparison')
    left_suffix, right_suffix, difference = selection
    ids = [AID + '__' + left_suffix, AID + '__' + right_suffix]
    pair = [reports.get(cid) for cid in ids]
    for cid, report in zip(ids, pair):
        require(isinstance(report, dict) and report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id') == cid and report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') == 'original_native_capture',
                'original accepted report required: ' + cid)
    left, right = [report['comparison_record'] for report in pair]
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(left.get(key) and left[key] == right.get(key),
                'changed fixed original condition: ' + key)
    cases = [next(case for case in CASES if case.name == suffix)
             for suffix in (left_suffix, right_suffix)]
    for record, case in zip((left, right), cases):
        require(record.get('route_variant') == case.route and
                record.get('designation_status') == case.designation,
                'original case variables differ')
        measured = record.get('measurement', {})
        require(measured.get('frame_count') == 900 and
                type(measured.get('overlap_frame_count')) is int and
                type(measured.get('terminal_center_within')) is bool and
                measured.get('official_designation_status') == case.designation,
                'original zone, body or designation evidence absent')
        require((measured['overlap_frame_count'] > 0) == (case.route != 'beside') and
                measured['terminal_center_within'] == (case.route == 'within'),
                'original route contrast not physically realized')
    if difference == 'route':
        require(cases[0].designation == cases[1].designation and
                left['designation_source_sha256'] == right['designation_source_sha256'] and
                left['marking_source_sha256'] == right['marking_source_sha256'],
                'original designation changed during route comparison')
        require(cases[0].route != cases[1].route,
                'declared route comparison did not change')
    else:
        require(cases[0].route == cases[1].route and
                cases[0].designation != cases[1].designation,
                'designation-source comparison changed route or did not change designation')
        require(left['designation_source_sha256'] != right['designation_source_sha256'],
                'original designation source contrast absent')
    return {
        'format': 'c412974-independent-original-comparison-v1',
        'comparison_id': comparison_id, 'case_ids': ids,
        'fixed_source_sha256': left['fixed_source_sha256'],
        'overlap_frame_counts': [left['measurement']['overlap_frame_count'],
                                 right['measurement']['overlap_frame_count']],
        'terminal_center_within': [left['measurement']['terminal_center_within'],
                                   right['measurement']['terminal_center_within']],
        'designation_statuses': [left['designation_status'], right['designation_status']],
        'physical_comparison_passed': True, 'legal_verdict_claimed': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text(encoding='utf-8'))
    reports = {cid: json.loads(Path(path).read_text(encoding='utf-8')) for cid, path in paths.items()}
    result = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
