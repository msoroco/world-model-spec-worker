"""Independent saved-original audit of center-lane turn versus straight use."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from straight_use_measurement import measure
from turn_origin_comparison_audit import _source as turn_source

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
            context.get('requested_maneuver') != 'straight' or
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


def audit(left_root, straight_root, *, decode_video=True):
    left = turn_source(left_root, PREFIX+'left_center_east',
                       decode_video=decode_video)
    straight = _source(straight_root, PREFIX+'straight_center_east',
                       decode_video=decode_video)
    a, b = left['measurement'], straight['measurement']
    fixed = ('approach_road_id', 'approach_lane_id', 'center_turn_lane_id',
             'center_marking_source_ids', 'designation_source')
    if (not a['origin_matches_center_lane'] or
            not b['origin_matches_center_lane'] or
            any(a.get(key) != b.get(key) for key in fixed)):
        raise ValueError('Center-lane original fixed source condition differs')
    if (left['context'].get('requested_maneuver') != 'left turn' or
            straight['context'].get('requested_maneuver') != 'straight' or
            a['maximum_left_deflection_deg'] < 60 or
            not b['straight_motion_observed']):
        raise ValueError('Center-lane turn/straight difference not observed')
    if ([(r['is_junction'], r['time_s']-left['rows'][0]['time_s']) for r in left['rows']] !=
            [(r['is_junction'], r['time_s']-straight['rows'][0]['time_s']) for r in straight['rows']]):
        raise ValueError('Original center-use junction/time schedule differs')
    for source in (left, straight):
        if [cam['name'] for cam in source['config']['cameras']] != list(CAMERAS):
            raise ValueError('Original four-camera contract differs')
    return {'format': 'worker-independent-comparison-audit',
            'comparison_id': 'center_use',
            'left_case_id': PREFIX+'left_center_east',
            'straight_case_id': PREFIX+'straight_center_east',
            'left_source_hashes': left['hashes'],
            'straight_source_hashes': straight['hashes'],
            'fixed_conditions': ['candidate center road/lane and map-marking references',
                                 'original junction/time schedule',
                                 'four named full-decoded camera sources'],
            'observed_difference': {'left_maneuver': left['context']['requested_maneuver'],
                                    'straight_maneuver': straight['context']['requested_maneuver'],
                                    'left_deflection_deg': a['maximum_left_deflection_deg'],
                                    'straight_deflection_deg': b['maximum_deflection_deg']},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--straight', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.left, args.straight)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison proof')
    output.write_text(json.dumps(result, indent=2)+'\n')
