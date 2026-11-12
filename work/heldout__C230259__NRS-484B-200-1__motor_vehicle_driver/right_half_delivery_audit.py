"""Independent saved-source delivery audit for exact right-half baseline cases."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import subprocess

from right_half_measurement import measure

PREFIX = 'heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__baseline_'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original delivery source: ' + name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(attempt, report):
    root = Path(attempt)
    config = json.loads(_source(root, 'config.json').read_text())
    case = config.get('selected_case_id')
    if case not in (PREFIX + 'right', PREFIX + 'left',
                    PREFIX.replace('baseline_', '') + 'passing_left',
                    PREFIX.replace('baseline_', '') + 'closure_left',
                    PREFIX.replace('baseline_', '') + 'three_lane_left',
                    PREFIX.replace('baseline_', '') + 'one_way_left',
                    PREFIX.replace('baseline_', '') + 'narrow_left'):
        raise ValueError('Wrong exact baseline delivery identity')
    report_value = json.loads(Path(report).read_text())
    if report_value.get('case_id') != case:
        raise ValueError('Saved analysis report selects another case')
    names = ('ego_road_frames.jsonl', 'road_exception_context.json',
             'video_frames.jsonl', 'trace.jsonl')
    sources = {name: _source(root, name) for name in names}
    value = measure(sources[names[0]], sources[names[1]])
    claimed = report_value.get('measurements', {}).get('right_half_observation', {})
    if claimed.get('value') != value:
        raise ValueError('Saved right-half measurement differs from original sources')
    if claimed.get('sources') != {name: _hash(path) for name, path in sources.items()}:
        raise ValueError('Saved source hashes differ')
    road, mapping, trace = (_rows(sources[name]) for name in
                            (names[0], names[2], names[3]))
    if not road or len(road) != len(mapping) or len(road) != len(trace):
        raise ValueError('Original delivery frame counts differ')
    for i, (body, frame, sample) in enumerate(zip(road, mapping, trace)):
        if (frame.get('video_frame') != i or
                (body['frame'], body['time_s']) != (frame['carla_frame'], frame['time_s']) or
                (sample['frame'], sample['time_s']) != (frame['carla_frame'], frame['time_s'])):
            raise ValueError('Original delivery frame/time join differs')
    wanted = 'whole_body_right_half' if case.endswith('_right') else 'whole_body_left_half'
    if case.endswith('__passing_left'):
        sides = value['observations']
        setup = json.loads(sources['road_exception_context.json'].read_text()).get('passing_setup')
        if (not isinstance(setup, dict) or setup.get('subject_path') != 'right_left_right' or
                not all(row['whole_body_right_half'] for row in sides[:2]) or
                not any(row['whole_body_left_half'] for row in sides[2:-1]) or
                not sides[-1]['whole_body_right_half']):
            raise ValueError('Original passing excursion and return absent')
        wanted = 'right_to_left_to_right_excursion'
    elif not all(row[wanted] for row in value['observations']):
        raise ValueError('Original body did not occupy requested baseline half')
    closure_sha = None
    if case.endswith('__closure_left'):
        closure = _source(root, 'closure_devices.jsonl')
        closure_sha = _hash(closure)
        device_rows = _rows(closure)
        setup = json.loads(sources['road_exception_context.json'].read_text()).get('closure_setup')
        if (len(device_rows) != len(road) or not isinstance(setup, dict) or
                setup.get('right_half_closure_authority') != 'undecided' or
                setup.get('subject_path') != 'left_half'):
            raise ValueError('Original closure setup/source missing')
        expected_ids = [str(item) for item in setup.get('device_actor_ids', [])]
        positions = None
        for body, row in zip(road, device_rows):
            devices = row.get('devices', [])
            if (row.get('frame'), row.get('time_s')) != (body['frame'], body['time_s']) or row.get('authority_verified') is not False:
                raise ValueError('Original closure frame or authority differs')
            if len(devices) != 3 or [item.get('actor_id') for item in devices] != expected_ids:
                raise ValueError('Original closure actor IDs differ')
            current = [item.get('position_m') for item in devices]
            if positions is None:
                positions = current
            elif current != positions:
                raise ValueError('Original closure devices moved between frames')
            center = body['road_center_xy']
            tangent = body['road_travel_tangent_xy']
            width = body['road_width_m']
            for point in current:
                lateral = tangent[0] * (point[1] - center[1]) - tangent[1] * (point[0] - center[0])
                if not -width / 2 < lateral < 0:
                    raise ValueError('Original closure device outside right half')
        wanted = 'whole_body_left_half_beside_three_right_half_devices'
    if case.endswith('__three_lane_left'):
        setup = json.loads(sources['road_exception_context.json'].read_text()).get('three_lane_setup')
        if (not isinstance(setup, dict) or setup.get('applicable_lane_rule') != 'undecided' or
                setup.get('subject_path') != 'left_half'):
            raise ValueError('Original three-lane setup missing or pre-decided')
        expected_ids = setup.get('lane_ids')
        for body in road:
            lanes = body.get('lane_inventory')
            if (not isinstance(lanes, list) or len(lanes) != 3 or
                    [lane.get('lane_id') for lane in lanes] != expected_ids or
                    body.get('applicable_lane_rule_verified') is not False or
                    sum(lane.get('width_m', 0) for lane in lanes) != body['road_width_m']):
                raise ValueError('Original three-lane inventory or width differs')
            directed = body['road_travel_tangent_xy']
            dots = [sum(a * b for a, b in zip(directed, lane['travel_tangent_xy']))
                    for lane in lanes]
            if not (dots[0] > .95 and dots[1] > .95 and dots[2] < -.95):
                raise ValueError('Original three-lane direction pattern differs')
        wanted = 'whole_body_left_half_on_three_lanes'
    sign_sha = None
    if case.endswith('__one_way_left'):
        sign_path = _source(root, 'one_way_sign.jsonl')
        sign_sha = _hash(sign_path)
        signs = _rows(sign_path)
        setup = json.loads(sources['road_exception_context.json'].read_text()).get('one_way_setup')
        if (not isinstance(setup, dict) or setup.get('official_designation') != 'undecided' or
                setup.get('posting_authority') != 'undecided' or
                setup.get('subject_path') != 'left_half' or len(signs) != len(road)):
            raise ValueError('Original one-way setup or sign source missing')
        sign_position = None
        for body, sign in zip(road, signs):
            lanes = body.get('lane_inventory')
            if (not isinstance(lanes, list) or len(lanes) != 2 or
                    [lane.get('lane_id') for lane in lanes] != setup.get('lane_ids') or
                    sum(lane.get('width_m', 0) for lane in lanes) != body['road_width_m'] or
                    body.get('designation_verified') is not False or
                    body.get('posting_authority_verified') is not False):
                raise ValueError('Original one-way lane inventory differs')
            tangent = body['road_travel_tangent_xy']
            if not all(sum(a * b for a, b in zip(tangent, lane['travel_tangent_xy'])) > .95
                       for lane in lanes):
                raise ValueError('Original one-way lane direction differs')
            if ((sign.get('frame'), sign.get('time_s')) != (body['frame'], body['time_s']) or
                    sign.get('actor_id') != str(setup.get('sign_actor_id')) or
                    'oneway' not in sign.get('blueprint_id', '').lower().replace('_', '') or
                    sign.get('designation_verified') is not False or
                    sign.get('posting_authority_verified') is not False):
                raise ValueError('Original one-way sign identity/frame/authority differs')
            if sign_position is None:
                sign_position = sign.get('position_m')
            elif sign.get('position_m') != sign_position:
                raise ValueError('Original one-way sign moved between frames')
        wanted = 'whole_body_left_half_on_two_same_direction_lanes_with_sign'
    if case.endswith('__narrow_left'):
        setup = json.loads(sources['road_exception_context.json'].read_text()).get('narrow_setup')
        if (not isinstance(setup, dict) or setup.get('legal_sufficiency') != 'undecided' or
                setup.get('subject_path') != 'left_half' or
                setup.get('candidate_max_road_width_m') != 6.5 or
                setup.get('subject_body_width_m', 0) <= 0):
            raise ValueError('Original narrow-width setup missing or pre-decided')
        for body in road:
            width = body['road_width_m']
            if (width > 6.5 or body.get('narrow_candidate_width_m') != width or
                    body.get('legal_sufficiency_decided') is not False):
                raise ValueError('Original narrow-width road source differs')
            points = body['ego_corners_xy']
            edges = [hypot(b[0] - a[0], b[1] - a[1]) for a in points for b in points if a != b]
            if abs(min(edges) - setup['subject_body_width_m']) > .1:
                raise ValueError('Original narrow-width body source differs')
        if any(width > 6.5 for width in setup.get('selected_road_widths_m', [])):
            raise ValueError('Original selected route exceeds narrow screen')
        wanted = 'whole_body_left_half_on_measured_narrow_road'
    videos = {}
    for name in CAMERAS:
        path = _source(root, name + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,codec_name', '-of', 'json',
                                str(path)], capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or int(streams[0].get('nb_read_frames', -1)) != len(road):
            raise ValueError('Original camera frame/codec differs: ' + name)
        decoded = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel',
                                  'error', '-i', str(path), '-map', '0:v:0',
                                  '-f', 'null', '-'], capture_output=True, text=True)
        if decoded.returncode or decoded.stderr:
            raise ValueError('Original camera full decode failed: ' + name)
        videos[name] = _hash(path)
    return {'format': 'worker-right-half-delivery-audit', 'case_id': case,
            'frames': len(road), 'source_sha256': {name: _hash(path) for name,path in sources.items()},
            'source_video_sha256': videos, 'closure_source_sha256': closure_sha,
            'one_way_sign_source_sha256': sign_sha,
            'body_side_observed': wanted,
            'originals_joined': True, 'analysis_recomputed': True,
            'four_camera_full_decode': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.report)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'frames': result['frames']}))
