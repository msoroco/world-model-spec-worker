"""Independent original-only sidewalk body and exception comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AID = 'testing__C229462__NRS-484B-450-1a__motor_vehicle_driver'
PAIRS = {
    'footprint_overlap': ('park_on_sidewalk', 'park_off_sidewalk'),
    'boundary_touch': ('park_on_sidewalk', 'park_edge_touch'),
    'traffic_necessity_exception': ('park_on_sidewalk', 'on_sidewalk_traffic_necessity'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown sidewalk comparison')
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
    require(x.get('frame_count') == y.get('frame_count') == 900, 'original frame count differs')
    ox, oy = x.get('terminal_mean_sidewalk_body_overlap_m2'), y.get('terminal_mean_sidewalk_body_overlap_m2')
    dx, dy = x.get('terminal_boundary_distance_m'), y.get('terminal_boundary_distance_m')
    require(all(type(v) in (int, float) for v in (ox, oy, dx, dy)), 'original body measurements absent')
    if comparison_id == 'footprint_overlap':
        require(a['requested_relation'] == 'overlap' and b['requested_relation'] == 'separate' and
                ox > 0 and oy == 0 and dy > .05, 'sidewalk overlap contrast absent')
    elif comparison_id == 'boundary_touch':
        require(a['requested_relation'] == 'overlap' and b['requested_relation'] == 'touch' and
                ox > 0 and oy == 0 and dy <= .05, 'sidewalk boundary touch absent')
    else:
        require(a['requested_relation'] == b['requested_relation'] == 'overlap' and
                a['traffic_context'] == 'absent' and b['traffic_context'] == 'unresolved' and
                ox > 0 and oy > 0 and abs(ox - oy) <= .1 and
                x['exception_context']['traffic_conflict_necessity'] == 'absent' and
                y['exception_context']['traffic_conflict_necessity'] == 'unresolved',
                'original traffic necessity context contrast absent')
    return {'format': 'c229462-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': case_ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'terminal_sidewalk_overlaps_m2': [ox, oy],
            'terminal_boundary_distances_m': [dx, dy],
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
