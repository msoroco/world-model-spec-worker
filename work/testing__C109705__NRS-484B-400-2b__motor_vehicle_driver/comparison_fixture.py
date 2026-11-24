"""Exercise fixed-approach departure comparison on explicit CPU geometry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from departure_geometry import measure
from comparison_audit import audit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def trace(case, departure_x, *, changed_approach=False):
    points = [(10, 0, 'approach', 'approach'),
              (8 if not changed_approach else 6, 0, 'approach', 'approach'),
              (1, 0, 'intersection_entry', 'approach'),
              (departure_x, -10, 'departure', 'destination')]
    samples = []
    for frame, (x, y, phase, road) in enumerate(points):
        corners = [[x - .5, y - .5], [x + .5, y - .5],
                   [x + .5, y + .5], [x - .5, y + .5]]
        samples.append({'frame': frame, 'phase': phase, 'road_id': road,
                        'position_xy_m': [x, y], 'body_corners_xy_m': corners,
                        'heading_rad': 3.141592653589793 if phase != 'departure' else -1.5707963267948966,
                        'speed_mps': 2.0,
                        'elapsed_seconds': frame / 20})
    return {'case_id': case, 'approach_road_id': 'approach',
            'destination_road_id': 'destination', 'maneuver': 'left_turn',
            'driver_control': True, 'samples': samples}


def run(pair, scratch, output):
    root = Path(scratch).resolve()
    if '.runtime-work' not in root.parts or root.exists():
        raise ValueError('Use fresh comparison fixture scratch under .runtime-work')
    root.mkdir(parents=True)
    imaginary = pair == 'imaginary'
    names = (('imaginary_near_centerline', 'imaginary_farther_from_centerline')
             if imaginary else ('near_centerline', 'farther_from_centerline'))
    cases = [HERE.name + '__' + name for name in names]
    map_packet = {
        'case_ids': cases, 'road_kind': 'two_directional_intersection',
        'approach_road_id': 'approach', 'destination_road_id': 'destination',
        'approach_two_directional': True, 'destination_two_directional': True,
        'approach_highway_status': 'source_verified',
        'destination_highway_status': 'source_verified',
        'centerline_kind': 'source_derived_imaginary' if imaginary else 'mapped',
        'centerline_origin_xy_m': [0, 0], 'destination_direction_xy': [0, -1],
        'centerline_source': 'synthetic comparison geometry',
        'direction_source': 'synthetic comparison geometry',
    }
    map_path = root / 'map.json'
    write(map_path, map_packet)
    reports = []
    for index, case in enumerate(cases):
        trace_path = root / f'trace-{index}.json'
        write(trace_path, trace(case, -1 if index == 0 else -3))
        report = measure(map_packet, json.loads(trace_path.read_text()), case_id=case)
        report['sources'] = [{'path': str(map_path), 'sha256': sha(map_path)},
                             {'path': str(trace_path), 'sha256': sha(trace_path)}]
        path = root / f'report-{index}.json'
        write(path, report)
        reports.append(path)
    kind = map_packet['centerline_kind']
    result = audit(*reports, expected_near=cases[0], expected_far=cases[1],
                   expected_centerline_kind=kind)
    write(output, {'format': 'worker-diagnostic-comparison-cpu',
                   'pair': pair, 'comparison': result,
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False})
    changed = root / 'trace-1.json'
    write(changed, trace(cases[1], -3, changed_approach=True))
    report = json.loads(reports[1].read_text())
    report['sources'][1]['sha256'] = sha(changed)
    write(reports[1], report)
    try:
        audit(*reports, expected_near=cases[0], expected_far=cases[1],
              expected_centerline_kind=kind)
    except ValueError as exc:
        if 'comparison original approach trajectory changed' not in str(exc):
            raise
        print(json.dumps({'pair': pair, 'positive': True,
                          'negative_error': str(exc), 'diagnostic_fixture': True}, sort_keys=True))
    else:
        raise ValueError('changed approach escaped independent comparison audit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', choices=('mapped', 'imaginary'), required=True)
    parser.add_argument('--scratch', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.pair, args.scratch, args.output)


if __name__ == '__main__':
    main()
