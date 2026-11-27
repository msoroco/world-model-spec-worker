"""Independent original-only sidewalk, entrance and subsection (2) comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AID = 'testing__C412982__NRS-484B-117-1__motor_vehicle_driver'
PAIRS = {
    'road_vs_sidewalk': ('ordinary_road_travel', 'ordinary_sidewalk_travel'),
    'permanent_driveway': ('ordinary_sidewalk_travel', 'permanent_driveway_crossing'),
    'temporary_driveway': ('ordinary_sidewalk_travel', 'temporary_driveway_crossing'),
    'alley_entrance': ('ordinary_sidewalk_travel', 'alley_entrance_crossing'),
    'three_wheel_prerequisite': ('ordinary_sidewalk_travel', 'electric_three_wheel_no_duty'),
    'emergency_exception': ('electric_three_wheel_no_duty', 'electric_three_wheel_emergency'),
    'law_officer_exception': ('electric_three_wheel_no_duty', 'electric_three_wheel_law_officer'),
    'security_exception': ('electric_three_wheel_no_duty', 'electric_three_wheel_security_guard'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown sidewalk comparison')
    ids = [AID + '__' + suffix for suffix in suffixes]
    left, right = (reports.get(case_id) for case_id in ids)
    for case_id, report in zip(ids, (left, right)):
        require(isinstance(report, dict) and
                report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and
                report.get('protocol_fixture_checked') is False and
                report.get('physical_acceptance_claimed') is True and
                report.get('case_id') == case_id and
                report.get('frame_count') == 900 and
                report.get('comparison_record', {}).get('source_kind') ==
                'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = left['comparison_record'], right['comparison_record']
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(a.get(key) and a.get(key) == b.get(key),
                'changed fixed original condition: ' + key)
    require(a.get('frame_count') == b.get('frame_count') == 900,
            'original frame count differs')
    x, y = (a.get('maximum_sidewalk_body_overlap_m2'),
            b.get('maximum_sidewalk_body_overlap_m2'))
    require(all(type(v) in (int, float) for v in (x, y)),
            'original sidewalk body measurements absent')
    if comparison_id == 'road_vs_sidewalk':
        require(a['vehicle_design'] == b['vehicle_design'] and
                a['operator_context']['role'] == b['operator_context']['role'] and
                x == 0 and y > 0, 'road versus sidewalk contrast absent')
    elif comparison_id in ('permanent_driveway', 'temporary_driveway', 'alley_entrance'):
        kind = {'permanent_driveway': 'permanent_driveway',
                'temporary_driveway': 'temporary_driveway',
                'alley_entrance': 'alley_entrance'}[comparison_id]
        ax = a.get('maximum_entrance_body_overlap_m2', {}).get(kind)
        by = b.get('maximum_entrance_body_overlap_m2', {}).get(kind)
        require(a['vehicle_design'] == b['vehicle_design'] and
                a['operator_context']['role'] == b['operator_context']['role'] and
                x > 0 and y > 0 and ax == 0 and type(by) in (int, float) and by > 0,
                'original entrance contrast absent')
    elif comparison_id == 'three_wheel_prerequisite':
        design = b['vehicle_design']
        require(x > 0 and y > 0 and
                a['operator_context']['role'] == b['operator_context']['role'] == 'ordinary' and
                a['vehicle_design']['power'] == 'combustion' and
                design['power'] == 'solely_electric' and
                design['wheel_count'] == design['designed_for_wheel_count'] == 3,
                'electric three-wheel prerequisite contrast absent')
    else:
        role = {'emergency_exception': 'emergency',
                'law_officer_exception': 'law_officer',
                'security_exception': 'security_guard'}[comparison_id]
        context = b['operator_context']
        require(x > 0 and y > 0 and
                a['body_geometry_source_sha256'] == b['body_geometry_source_sha256'] and
                a['vehicle_design'] == b['vehicle_design'] and
                a['operator_context']['role'] == 'ordinary' and
                context['role'] == role and context.get('authorized') is True and
                (role == 'emergency' and
                 context.get('operated_as_authorized_emergency_vehicle') is True or
                 role != 'emergency' and context.get('on_official_duty') is True),
                'original authorized duty contrast absent')
    return {'format': 'c412982-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'maximum_sidewalk_body_overlap_m2': [x, y],
            'physical_comparison_passed': True, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {case_id: json.loads(Path(path).read_text()) for case_id, path in paths.items()}
    selected = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, indent=2) + '\n')
    print(json.dumps(selected))


if __name__ == '__main__':
    main()
