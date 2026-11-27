"""Independent original-only tunnel boundary, activity and exception contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tunnel import CASES

AID = 'testing__C312865__NRS-484B-450-1m__motor_vehicle_driver'
PAIRS = {
    'portal_location': ('outside_stop', 'inside_stop'),
    'activity_stand': ('inside_stop', 'inside_stand'),
    'activity_park': ('inside_stop', 'inside_park'),
    'necessary_conflict': ('inside_stop', 'inside_conflict'),
    'law_direction': ('inside_stop', 'inside_law'),
    'police_direction': ('inside_stop', 'inside_police'),
    'official_device': ('inside_stop', 'inside_device')}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown tunnel comparison')
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
                 record.get('exception')) ==
                (case.endpoint, case.activity, case.exception_probe),
                'original tunnel case variables differ')
    x, y = a['measurement'], b['measurement']
    for row in (x, y):
        require(row.get('original_frames') == 900 and
                type(row.get('terminal_speed_mps')) in (int, float) and
                row['terminal_speed_mps'] <= .1,
                'original full tunnel halt measurement absent')
    if comparison_id == 'portal_location':
        require(left.endpoint == 'outside_before_portal' and right.endpoint == 'inside_tunnel' and
                left.activity == right.activity == 'stop' and
                x.get('terminal_body_outside_tunnel') is True and
                y.get('terminal_body_inside_tunnel') is True,
                'original portal boundary contrast absent')
    elif comparison_id in ('activity_stand', 'activity_park'):
        require(left.endpoint == right.endpoint == 'inside_tunnel' and
                left.exception_probe == right.exception_probe is None and
                left.activity != right.activity and
                x.get('terminal_body_inside_tunnel') is True and
                y.get('terminal_body_inside_tunnel') is True,
                'isolated ordinary tunnel halt activity contrast absent')
    else:
        require(left.endpoint == right.endpoint == 'inside_tunnel' and
                left.activity == right.activity == 'stop' and
                left.exception_probe is None and right.exception_probe is not None and
                x.get('terminal_body_inside_tunnel') is True and
                y.get('terminal_body_inside_tunnel') is True and
                y.get('original_exception_source_sha256'),
                'isolated tunnel exception source contrast absent')
    return {'format': 'c312865-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'terminal_inside': [x['terminal_body_inside_tunnel'],
                                y['terminal_body_inside_tunnel']],
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
