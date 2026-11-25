"""Exact C111250 intersection delivery entrypoint; CARLA loads only on execution."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    assignment = json.loads((bundle / 'assignment-source.json').read_text())
    case = config.get('case_id')
    suffix = case.rsplit('__', 1)[-1] if isinstance(case, str) else None
    if (assignment['assignment_id'] + '__' + suffix != case or
            suffix not in ('probe_01', 'probe_02', 'probe_03') or
            config.get('selected_case_id') != case or
            config.get('candidate_id') not in ('primary', 'fallback1') or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-213-2b', 'C111250', 'motor_vehicle_driver') or
            (config.get('rate_hz'), config.get('duration_frames')) != (20, 600)):
        raise ValueError('Exact C111250 identity or duration changed')
    for key, name in (('assignment_sha256', 'assignment-source.json'),
                      ('road_sha256', 'road.xodr')):
        if config.get(key) != sha(bundle / name):
            raise ValueError('Changed source: ' + name)
    if config.get('road_directionality') != 'two_way' or config.get('one_way_highway') is not False:
        raise ValueError('Two-way approach context changed')
    road = ET.parse(bundle / 'road.xodr').getroot()
    if len(road.findall('./junction')) != 1 or len(road.findall('./road')) < 5:
        raise ValueError('Constructed intersection missing')
    lanes = road.findall('.//laneSection/left/lane') + road.findall('.//laneSection/right/lane')
    if not {'-1', '1'}.issubset({lane.get('id') for lane in lanes}):
        raise ValueError('Two-way approach lanes missing')
    expected = {'probe_01': [], 'probe_02': [240, 359], 'probe_03': [400, 450]}[suffix]
    if config.get('requested_left_interval') != expected:
        raise ValueError('Exact lateral request changed')
    cameras = config.get('cameras', [])
    if [c.get('name') for c in cameras] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('Four source cameras missing')
    if any(c.get('fps') != 20 or c.get('width') != (1920 if c['name'] == 'overview' else 1280) or
           c.get('height') != (1080 if c['name'] == 'overview' else 720) for c in cameras):
        raise ValueError('Camera resolution or rate changed')
    return {'case_id': case, 'candidate_id': config['candidate_id'],
            'frames': 600, 'native_executed': False, 'legal_verdict': None}


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
    from selected_capture import execute
    execute(args.bundle, args.output_dir, args.host, args.port, checked)


if __name__ == '__main__':
    main()
