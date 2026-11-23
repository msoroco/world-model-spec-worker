"""Measure a pedestrian's road entry from retained, synchronized sources.

This is a CPU saved-source measurement, not a legal verdict or Native capture.
The road boundary and signal applicability must be calibrated from Native data
before this can support a selected delivery case.
"""

import argparse
import json
from pathlib import Path


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
RATE_HZ = 20


def read_json(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return json.loads(path.read_text())


def read_rows(path, index_key='frame'):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows:
        raise ValueError('Empty required source: ' + path.name)
    frames = [row[index_key] for row in rows]
    if frames != list(range(len(rows))):
        raise ValueError('Source frames must be continuous from zero: ' + path.name)
    return rows


def measure(folder, diagnostic_fixture=False):
    folder = Path(folder)
    geometry = read_json(folder / 'road-boundary.json')
    expected_kind = 'synthetic_native_sample' if diagnostic_fixture else None
    if geometry.get('format') != 'pedestrian-road-boundary-v1' or \
            geometry.get('road_side') not in ('at_or_above_y', 'at_or_below_y') or \
            not isinstance(geometry.get('boundary_y_m'), (float, int)) or \
            geometry.get('source_kind') != (expected_kind or 'native_map_readback'):
        raise ValueError('Invalid Native road-boundary calibration')
    pedestrian = read_rows(folder / 'native-pedestrian-frames.jsonl')
    signals = read_rows(folder / 'native-signal-frames.jsonl')
    permissions = read_rows(folder / 'native-pedestrian-device-frames.jsonl')
    footage = read_rows(folder / 'video_frames.jsonl', 'video_frame')
    count = len(pedestrian)
    if any(len(rows) != count for rows in (signals, permissions, footage)):
        raise ValueError('Source frame counts disagree')
    first_time = footage[0].get('time_s')
    if type(first_time) not in (int, float):
        raise ValueError('Missing original capture timestamp')
    inside = []
    for frame in range(count):
        actor, signal, permit, video = (rows[frame] for rows in
                                        (pedestrian, signals, permissions, footage))
        times = [row.get('time_s') for row in (actor, signal, permit, video)]
        if any(type(value) not in (int, float) for value in times) or \
                max(times) - min(times) > 0.001 or \
                abs(times[0] - (first_time + frame / RATE_HZ)) > 0.001:
            raise ValueError('Source timestamps do not join at frame ' + str(frame))
        native_frame = video.get('native_frame')
        if type(native_frame) is not int or native_frame != video.get('carla_frame') or \
                any(row.get('native_frame') != native_frame
                    for row in (actor, signal, permit)):
            raise ValueError('Native frame identities do not join at frame ' + str(frame))
        pixels = video.get('source_rgb_sha256')
        if not isinstance(pixels, dict) or set(pixels) != set(VIEWS) or \
                any(not isinstance(value, str) or len(value) != 64 or
                    any(char not in '0123456789abcdef' for char in value)
                    for value in pixels.values()):
            raise ValueError('Missing four-camera frame join at frame ' + str(frame))
        if type(actor.get('actor_id')) is not int or \
                actor.get('actor_id') != pedestrian[0].get('actor_id') or \
                actor.get('source_kind') != (expected_kind or 'native_actor') or \
                type(actor.get('footprint_roadward_y_m')) not in (int, float):
            raise ValueError('Invalid Native pedestrian sample')
        if signal.get('source_kind') != (expected_kind or 'native_signal') or \
                type(signal.get('governs_pedestrian')) is not bool or \
                signal.get('red') not in ('steady', 'other') or \
                type(signal.get('green_turn_arrow')) is not bool:
            raise ValueError('Invalid governing signal sample')
        if not diagnostic_fixture and (signal.get('directional_arrow_pixels_verified') is not True or
                                       signal.get('facing_governance_verified') is not True):
            raise ValueError('Native signal pixel/governance review incomplete')
        if permit.get('source_kind') != (expected_kind or 'native_pedestrian_device') or \
                type(permit.get('permits_proceed')) is not bool:
            raise ValueError('Invalid pedestrian-device sample')
        if not diagnostic_fixture and permit.get('permission_reviewed') is not True:
            raise ValueError('Native pedestrian-device permission review incomplete')
        y = actor['footprint_roadward_y_m']
        boundary = geometry['boundary_y_m']
        inside.append(y >= boundary if geometry['road_side'] == 'at_or_above_y'
                      else y <= boundary)
    entries = []
    for frame in range(1, count):
        if not inside[frame - 1] and inside[frame]:
            signal, permit = signals[frame], permissions[frame]
            entries.append({
                'frame': frame, 'time_s': pedestrian[frame]['time_s'],
                'steady_red_with_green_turn_arrow_faces_pedestrian':
                    signal['governs_pedestrian'] and signal['red'] == 'steady'
                    and signal['green_turn_arrow'],
                'other_pedestrian_device_permits_proceed': permit['permits_proceed'],
            })
    return {
        'format': 'c228133-road-entry-measurement-v1',
        'frame_count': count, 'rate_hz': RATE_HZ,
        'entry_events': entries,
        'potential_9c_entry_frames': [item['frame'] for item in entries
            if item['steady_red_with_green_turn_arrow_faces_pedestrian']
            and not item['other_pedestrian_device_permits_proceed']],
        'sources': ['road-boundary.json', 'native-pedestrian-frames.jsonl',
                    'native-signal-frames.jsonl',
                    'native-pedestrian-device-frames.jsonl', 'video_frames.jsonl'],
        'source_kind': expected_kind or 'native_source_contract',
        'original_native_observed': False,
        'diagnostic_fixture': diagnostic_fixture,
        'legal_verdict': None,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    result = measure(args.attempt, args.diagnostic_fixture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
