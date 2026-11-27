"""Exact C245490 change-lane Native entrypoint; CARLA loads only on execution."""
import argparse
import hashlib
import json
from pathlib import Path

from signal_scene import CASE_SUFFIXES, request, verify_road


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    assignment = json.loads((bundle / 'assignment-source.json').read_text())
    case = config.get('selected_case_id')
    if not isinstance(case, str) or not case.startswith(assignment['assignment_id'] + '__'):
        raise ValueError('Exact assignment or case changed')
    suffix = case.rsplit('__', 1)[-1]
    if suffix not in CASE_SUFFIXES:
        raise ValueError('Unselected signal variant')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-413-2', 'C245490', 'motor_vehicle_driver'):
        raise ValueError('Law, cell or actor changed')
    expected = request(suffix)
    for name in ('area_class_requested', 'signal_onset_odometer_m',
                 'course_change_request_odometer_m', 'frames', 'rate_hz',
                 'duration_s', 'maneuver', 'layout', 'control', 'signal_side',
                 'weather_requested', 'interruption_requested', 'case_variant',
                 'requested_signal_distance_ft'):
        if config.get(name) != expected[name]:
            raise ValueError('Exact signal and lane-change request changed: ' + name)
    if set(config.get('supported_case_ids', [])) != {
            assignment['assignment_id'] + '__' + value for value in CASE_SUFFIXES}:
        raise ValueError('Incomplete twelve-case selection')
    for key, name in (('assignment_sha256', 'assignment-source.json'),
                      ('road_sha256', 'road.xodr')):
        if config.get(key) != sha(bundle / name):
            raise ValueError('Changed source: ' + name)
    verify_road((bundle / 'road.xodr').read_text())
    cameras = config.get('cameras', [])
    if [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] != [
            ('overview', 1920, 1080), ('approach', 1280, 720),
            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
        raise ValueError('Four canonical camera sources changed')
    return {'case_id': case, 'frames': 600, 'rate_hz': 20,
        'native_executed': False, 'area_class_originally_verified': False,
        'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    checked = check(args.bundle)
    if args.check:
        print(json.dumps(checked))
        return
    if not args.output_dir or not args.host or not args.port:
        parser.error('Native output, host and port required')
    from native_capture import run
    run(args.bundle, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
