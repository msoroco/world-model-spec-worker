"""Independent saved-original audit of the eastbound center/outer turn pair."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from turn_origin_measurement import measure

PREFIX = 'heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _required(root, name):
    path = Path(root)/name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing required source: '+name)
    return path


def _decode(path):
    run = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                          '-f', 'null', '-'], capture_output=True, text=True)
    if run.returncode or run.stderr.strip():
        raise ValueError('Original four-camera full decode failed: '+path.name)


def _source(root, expected_case, *, decode_video):
    root = Path(root)
    config = json.loads(_required(root, 'config.json').read_text())
    context = json.loads(_required(root, 'case_context.json').read_text())
    if ((config.get('selected_case_id'), config.get('actor'), config.get('law_id')) !=
            (expected_case, 'motor_vehicle_driver', 'LVMC-11-12-100-C') or
            context.get('case_id') != expected_case or
            context.get('requested_maneuver') != 'left turn' or
            context.get('designation_authority_verified') is not False):
        raise ValueError('Original comparison case/intent identity differs')
    lane_path = _required(root, 'turn_origin_native.jsonl')
    measurement = measure(lane_path)
    rows = [json.loads(line) for line in lane_path.read_text().splitlines()]
    frames = [json.loads(line) for line in _required(root, 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in _required(root, 'trace.jsonl').read_text().splitlines()]
    if len(rows) != len(frames) or len(rows) != len(trace):
        raise ValueError('Original comparison source counts differ')
    for index, (row, frame, packet) in enumerate(zip(rows, frames, trace)):
        identity = row['frame'], row['time_s']
        if (frame.get('video_frame') != index or
                (frame.get('carla_frame'), frame.get('time_s')) != identity or
                (packet.get('frame'), packet.get('time_s')) != identity):
            raise ValueError('Original comparison time/frame join differs')
    hashes = {name: sha256(_required(root, name).read_bytes()).hexdigest()
              for name in ('config.json', 'case_context.json', 'turn_origin_native.jsonl',
                           'video_frames.jsonl', 'trace.jsonl')}
    if decode_video:
        for name in CAMERAS:
            filename = name+'.mkv'
            path = _required(root, filename)
            _decode(path)
            hashes[filename] = sha256(path.read_bytes()).hexdigest()
    return {'config': config, 'context': context, 'measurement': measurement,
            'rows': rows, 'hashes': hashes}


def audit(center_root, outer_root, *, decode_video=True):
    center = _source(center_root, PREFIX+'left_center_east', decode_video=decode_video)
    outer = _source(outer_root, PREFIX+'left_outer_east', decode_video=decode_video)
    a, b = center['measurement'], outer['measurement']
    if (not a['origin_matches_center_lane'] or b['origin_matches_center_lane'] or
            a['approach_road_id'] != b['approach_road_id'] or
            a['center_turn_lane_id'] != b['center_turn_lane_id'] or
            a['approach_lane_id'] == b['approach_lane_id'] or
            a['center_marking_source_ids'] != b['center_marking_source_ids'] or
            a['designation_source'] != b['designation_source']):
        raise ValueError('Center/outer origin or fixed marking condition differs')
    fixed_context = ('target_exit_road_id', 'target_exit_lane_id',
                     'requested_maneuver', 'designation_authority_verified')
    if any(center['context'].get(key) != outer['context'].get(key) for key in fixed_context):
        raise ValueError('Left-turn target or authored fixed condition differs')
    if ([(r['is_junction'], r['time_s']-center['rows'][0]['time_s']) for r in center['rows']] !=
            [(r['is_junction'], r['time_s']-outer['rows'][0]['time_s']) for r in outer['rows']]):
        raise ValueError('Original comparison junction/time schedule differs')
    for source in (center, outer):
        if [cam['name'] for cam in source['config']['cameras']] != list(CAMERAS):
            raise ValueError('Original four-camera contract differs')
    return {'format': 'worker-independent-comparison-audit',
            'comparison_id': 'east_turn_origin',
            'center_case_id': PREFIX+'left_center_east',
            'outer_case_id': PREFIX+'left_outer_east',
            'center_source_hashes': center['hashes'],
            'outer_source_hashes': outer['hashes'],
            'fixed_conditions': ['candidate center road/lane and map-marking references',
                                 'authored left-turn exit and original junction/time schedule',
                                 'four named full-decoded camera sources'],
            'observed_difference': {'center_origin_lane_id': a['approach_lane_id'],
                                    'outer_origin_lane_id': b['approach_lane_id']},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--center', required=True)
    parser.add_argument('--outer', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.center, args.outer)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison proof')
    output.write_text(json.dumps(result, indent=2)+'\n')
