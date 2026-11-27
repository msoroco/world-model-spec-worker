"""Independent controlled inside/outside prohibited-extent comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C135709__NRS-484B-490__motor_vehicle_driver'
COMPARISON = ASSIGNMENT + '__planned_comparison'
FIXED_SOURCES = ('road.xodr', 'source_context/highway.txt',
                 'source_context/narrow_designation.txt',
                 'source_context/official_authority.txt',
                 'source_context/device_erection.txt',
                 'source_context/device_content.txt',
                 'source_context/governed_extent.txt')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(comparison, left, right, output):
    require(comparison == COMPARISON, 'Unknown exact comparison')
    left, right, output = Path(left), Path(right), Path(output)
    configs = [json.loads((root / 'config.json').read_text()) for root in (left, right)]
    expected = [ASSIGNMENT + '__probe_01', ASSIGNMENT + '__probe_02']
    require([c['case_id'] for c in configs] == expected,
            'Comparison must join the selected outside/inside case pair')
    for name in FIXED_SOURCES:
        require(sha(left / name) == sha(right / name),
                'Fixed road or official-device source changed: ' + name)
    for key in ('law_id', 'cell_id', 'actor', 'frozen_cell', 'rate_hz',
                'duration_s', 'duration_frames', 'cameras', 'recording_description'):
        require(configs[0].get(key) == configs[1].get(key),
                'Fixed construction or camera policy changed: ' + key)
    require(configs[0]['parking_x_m'] == 35 and configs[1]['parking_x_m'] == 0 and
            configs[0]['parking_y_m'] == configs[1]['parking_y_m'],
            'Parking placement did not isolate the governed extent')
    reviews = [json.loads((root / 'road-review.json').read_text()) for root in (left, right)]
    for key in ('roadway_is_highway', 'narrow_highway_designated',
                'device_is_official', 'device_erected', 'device_prohibits_parking',
                'governed_extent_xyxy_m', 'measured_road_width_m', 'device_id',
                'governed_road_id'):
        require(reviews[0].get(key) == reviews[1].get(key),
                'Reviewed law activation changed: ' + key)
    poses = [rows(root / 'vehicle-pose.jsonl') for root in (left, right)]
    maps = [rows(root / 'video_frames.jsonl') for root in (left, right)]
    require(all(len(part) == 600 for part in poses + maps),
            'Comparison lacks complete original 600-frame sources')
    for i in range(600):
        a, b = poses[0][i], poses[1][i]
        require(a['video_frame'] == b['video_frame'] == i and
                a['native_frame'] == maps[0][i]['native_frame'] and
                b['native_frame'] == maps[1][i]['native_frame'] and
                abs(a['time_s'] - b['time_s']) < 1e-5 and
                a['speed_mps'] <= .1 and b['speed_mps'] <= .1 and
                a['bbox_half_length_m'] == b['bbox_half_length_m'] and
                a['bbox_half_width_m'] == b['bbox_half_width_m'] and
                abs(a['x_m'] - b['x_m'] - 35) < 1e-5 and
                abs(a['y_m'] - b['y_m']) < 1e-5,
                'Original parked frame or isolated x displacement differs')
    x0, y0, x1, y1 = reviews[0]['governed_extent_xyxy_m']
    def inside(p):
        return x0 <= p['x_m'] - p['bbox_half_length_m'] and p['x_m'] + p['bbox_half_length_m'] <= x1 and \
               y0 <= p['y_m'] - p['bbox_half_width_m'] and p['y_m'] + p['bbox_half_width_m'] <= y1
    require(not any(inside(p) for p in poses[0]) and all(inside(p) for p in poses[1]),
            'Full parked footprints do not realize the governed-extent contrast')
    report = {'format': 'c135709-comparison-audit-v1', 'comparison_id': comparison,
              'case_ids': expected,
              'checks': {'fixed_road_device_sources': True,
                         'fixed_construction_cameras_duration': True,
                         'fixed_reviewed_activation': True,
                         'full_original_frame_join': True,
                         'isolated_x_placement': True,
                         'outside_vs_inside_full_footprint': True},
              'passed': True,
              'diagnostic_fixture': all(r.get('synthetic_diagnostic') for r in reviews),
              'physical_or_legal_acceptance': False,
              'source_sha256': [{name: sha(root / name) for name in
                                 ('road.xodr', 'road-review.json', 'vehicle-pose.jsonl',
                                  'video_frames.jsonl')} for root in (left, right)]}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison_id': comparison, 'passed': True,
                      'diagnostic_fixture': report['diagnostic_fixture']}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    audit(args.comparison, args.left, args.right, args.output)
