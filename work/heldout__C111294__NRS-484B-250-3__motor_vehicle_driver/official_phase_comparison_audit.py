"""Independent original-source comparison of two governing device phases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(red_attempt, green_attempt):
    red, green = Path(red_attempt), Path(green_attempt)
    fixed = ('intersection_topology.json', 'intersection_participants.jsonl',
             'video_frames.jsonl', 'trace.jsonl',
             'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
             'driver_reference.mkv')
    for name in fixed:
        if not (red / name).is_file() or not (green / name).is_file() or (
                digest(red / name) != digest(green / name)):
            raise ValueError('Official phase comparison fixed original source changed: ' + name)
    context_name = 'official_device_context.json'
    if digest(red / context_name) != digest(green / context_name):
        raise ValueError('Official phase comparison governing device changed')
    context = json.loads((red / context_name).read_text())
    if not context.get('opendrive_signal_id') or not context.get('affected_lane_id'):
        raise ValueError('Official phase comparison lacks source device identity')
    frame_map = rows(red / 'video_frames.jsonl')
    phases = []
    for root, expected in ((red, 'TrafficLightState.Red'),
                           (green, 'TrafficLightState.Green')):
        states = rows(root / 'official_device_states.jsonl')
        if not states or len(states) != len(frame_map):
            raise ValueError('Official phase comparison source length changed')
        for state, frame in zip(states, frame_map):
            if ((state.get('frame'), state.get('time_s')) !=
                    (frame.get('carla_frame'), frame.get('time_s')) or
                    state.get('device_id') != context.get('device_id') or
                    state.get('value') != state.get('native_state') or
                    state.get('native_state') != expected):
                raise ValueError('Official phase original state readback differs')
        phases.append(digest(root / 'official_device_states.jsonl'))
    return {'format': 'worker-official-phase-source-comparison',
            'comparison_id': 'official_device_red_green',
            'red_case': json.loads((red / 'config.json').read_text())['selected_case_id'],
            'green_case': json.loads((green / 'config.json').read_text())['selected_case_id'],
            'fixed_sources': {name: digest(red / name) for name in fixed},
            'device_context_sha256': digest(red / context_name),
            'red_state_sha256': phases[0], 'green_state_sha256': phases[1],
            'frames': len(frame_map), 'native_capture_claimed': False,
            'legal_device_status_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--red', required=True)
    parser.add_argument('--green', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.red, args.green)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'frames': result['frames']}))


if __name__ == '__main__':
    main()
