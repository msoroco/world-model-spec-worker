"""Independent original-only access-aisle controlled-comparison audit."""
from __future__ import annotations

import json
from pathlib import Path

AID = 'testing__C150072__LVMC-11-52-136__motor_vehicle_driver'
PAIRS = {
    'full_vs_partial': ('aisle_full_park', 'aisle_partial_park'),
    'aisle_vs_adjacent': ('aisle_full_park', 'adjacent_space_park'),
    'park_vs_loading': ('aisle_full_park', 'aisle_loading_stop'),
    'park_vs_travel': ('aisle_full_park', 'aisle_travel'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown access-aisle comparison')
    case_ids = [AID + '__' + suffix for suffix in suffixes]
    left, right = (reports.get(case_id) for case_id in case_ids)
    for case_id, report in zip(case_ids, (left, right)):
        require(isinstance(report, dict) and report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id') == case_id and report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') == 'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = left['comparison_record'], right['comparison_record']
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(a.get(key) and a.get(key) == b.get(key), 'changed fixed original condition: ' + key)
    x, y = a['measurement'], b['measurement']
    require(x.get('frame_count') == y.get('frame_count') == 900,
            'original measurement frame count differs')
    ox = x.get('terminal_mean_aisle_body_overlap_m2')
    oy = y.get('terminal_mean_aisle_body_overlap_m2')
    require(type(ox) in (int, float) and type(oy) in (int, float),
            'original body overlap measurement missing')
    if comparison_id == 'full_vs_partial':
        require(a['requested_activity'] == b['requested_activity'] == 'park' and
                a['requested_footprint'] == 'aisle_full' and b['requested_footprint'] == 'aisle_partial' and
                ox > oy > 0, 'full/partial body overlap contrast not measured')
    elif comparison_id == 'aisle_vs_adjacent':
        require(a['requested_activity'] == b['requested_activity'] == 'park' and
                a['requested_footprint'] == 'aisle_full' and b['requested_footprint'] == 'adjacent_space' and
                ox > 0 and oy == 0, 'aisle/adjacent body contrast not measured')
    elif comparison_id == 'park_vs_loading':
        require(a['requested_footprint'] == b['requested_footprint'] == 'aisle_full' and
                a['requested_activity'] == 'park' and b['requested_activity'] == 'loading_stop' and
                ox > 0 and oy > 0 and abs(ox - oy) <= .1,
                'park/loading physical activity contrast not isolated')
    else:
        require(a['requested_footprint'] == b['requested_footprint'] == 'aisle_full' and
                a['requested_activity'] == 'park' and b['requested_activity'] == 'travel' and
                ox > 0 and oy > 0 and x.get('terminal_max_speed_mps', 1) <= .1 and
                y.get('terminal_max_speed_mps', 0) > .1,
                'park/travel physical activity contrast not isolated')
    return {'format': 'c150072-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': case_ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'terminal_aisle_overlaps_m2': [ox, oy],
            'activities': [a['requested_activity'], b['requested_activity']],
            'physical_comparison_passed': True, 'legal_verdict_claimed': False}


def audit_comparisons(reports):
    require(isinstance(reports, dict) and set(reports) ==
            {AID + '__' + suffix for pair in PAIRS.values() for suffix in pair},
            'five exact original reports required')
    return [audit_pair(comparison_id, reports) for comparison_id in PAIRS]


def main():
    import argparse
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
