"""Measure source-recorded lamp and activation facts without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
REQUIRED = ('native_frame', 'time_s', 'utc_s', 'speed_mps', 'headlamp_lit',
            'tail_lamp_lit', 'headlamp_white', 'tail_lamp_red',
            'front_visible_ft', 'rear_visible_ft', 'discernible_500ft')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def measure(source, context):
    source, context = Path(source), Path(context)
    require(source.is_file() and context.is_file(), 'Original lighting source or context missing')
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    setup = json.loads(context.read_text())
    require(len(rows) == FRAMES, 'Expected 600 original lighting frames')
    require(setup.get('vehicle_class_source') and setup.get('clock_source') and
            setup.get('range_calibration_source') and
            setup.get('visibility_review_source'), 'Source provenance incomplete')
    sunset, sunrise = setup.get('sunset_utc_s'), setup.get('next_sunrise_utc_s')
    require(finite(sunset) and finite(sunrise) and sunrise > sunset + 3600,
            'Sunset and sunrise source invalid')
    require(setup.get('vehicle_covered') is True,
            'Vehicle coverage unresolved in source context')
    require(type(setup.get('headlamp_count')) is int and setup['headlamp_count'] >= 1 and
            setup.get('tail_lamp_rear_mounted') is True,
            'Lamp equipment placement or count unresolved')
    counts = {'motion_frames': 0, 'activation_frames': 0,
              'required_burning_frames': 0, 'headlamp_dark_frames': 0,
              'tail_lamp_dark_frames': 0, 'front_below_300ft_frames': 0,
              'rear_below_500ft_frames': 0, 'headlamp_nonwhite_frames': 0,
              'tail_lamp_nonred_frames': 0, 'night_window_frames': 0,
              'low_visibility_frames': 0}
    for index, row in enumerate(rows):
        require(all(key in row for key in REQUIRED),
                'Original lighting frame missing field at ' + str(index))
        require(row['native_frame'] == index and finite(row['time_s']) and
                abs(row['time_s'] - index / RATE_HZ) < 1e-6,
                'Original lighting frame join differs at ' + str(index))
        for key in ('utc_s', 'speed_mps', 'front_visible_ft', 'rear_visible_ft'):
            require(finite(row[key]), 'Nonfinite lighting measurement at ' + str(index))
        require(row['speed_mps'] >= 0 and row['front_visible_ft'] >= 0 and
                row['rear_visible_ft'] >= 0, 'Negative lighting measurement')
        for key in ('headlamp_lit', 'tail_lamp_lit', 'headlamp_white',
                    'tail_lamp_red', 'discernible_500ft'):
            require(type(row[key]) is bool, 'Nonboolean lighting observation at ' + str(index))
        require(abs(row['utc_s'] - (rows[0]['utc_s'] + row['time_s'])) < 1e-6,
                'Original lighting clock join differs at ' + str(index))
        moving = row['speed_mps'] > 0
        night = sunset + 1800 <= row['utc_s'] <= sunrise - 1800
        low_visibility = not row['discernible_500ft']
        active = night or low_visibility
        counts['motion_frames'] += moving
        counts['night_window_frames'] += night
        counts['low_visibility_frames'] += low_visibility
        counts['activation_frames'] += active
        counts['required_burning_frames'] += moving and active
        counts['headlamp_dark_frames'] += moving and active and not row['headlamp_lit']
        counts['tail_lamp_dark_frames'] += moving and active and not row['tail_lamp_lit']
        counts['front_below_300ft_frames'] += row['front_visible_ft'] < 300
        counts['rear_below_500ft_frames'] += row['rear_visible_ft'] < 500
        counts['headlamp_nonwhite_frames'] += not row['headlamp_white']
        counts['tail_lamp_nonred_frames'] += not row['tail_lamp_red']
    return {'format': 'c230241-source-lighting-measurement-v1',
            'source_kind': setup.get('source_kind', 'unreviewed_original'),
            'source_sha256': sha(source), 'context_sha256': sha(context),
            'frames': FRAMES, 'rate_hz': RATE_HZ, 'duration_s': FRAMES / RATE_HZ,
            'measurements': counts, 'statutory_front_ft': 300,
            'statutory_rear_ft': 500, 'sunset_offset_s': 1800,
            'sunrise_offset_s': -1800,
            'headlamp_count': setup['headlamp_count'],
            'tail_lamp_rear_mounted': setup['tail_lamp_rear_mounted'],
            'original_native_verified': False, 'physical_visibility_verified': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = measure(args.source, args.context)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': result['frames'], 'measurements': result['measurements']}))


if __name__ == '__main__':
    main()
