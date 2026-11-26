"""Measure full electric-bicycle pass and surface gap from joined original poses."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rectangle(center, dimensions):
    x, y = center
    length, width = dimensions
    return x - length / 2, x + length / 2, y - width / 2, y + width / 2


def surface_gap(a, b):
    dx = max(a[0] - b[1], b[0] - a[1], 0)
    dy = max(a[2] - b[3], b[2] - a[3], 0)
    return math.hypot(dx, dy)


def measure(folder):
    folder = Path(folder)
    context_path = require(folder, 'pass-context.json')
    pose_path = require(folder, 'participant-poses.jsonl')
    context = json.loads(context_path.read_text())
    if context['rider_class'] not in ('bicycle', 'electric_bicycle', 'electric_scooter'):
        raise ValueError('Rider class is outside exact statutory subjects')
    electric = context['rider_class'] == 'electric_bicycle'
    if electric:
        qualification = context.get('rider_qualification')
        if not isinstance(qualification, dict) or (
            qualification.get('wheels') not in (2, 3) or
            qualification.get('operable_pedals') is not True or
            qualification.get('saddle') is not True or
            qualification.get('assist_only_while_pedaling') is not True or
            qualification.get('assist_cutoff_mph') != 20 or
            qualification.get('moped') is not False or
            qualification.get('electric_scooter') is not False or
            type(qualification.get('motor_rated_watts')) not in (int, float) or
            not 0 < qualification['motor_rated_watts'] <= 750 or
            not qualification.get('source')):
            raise ValueError('Electric-bicycle qualifying source incomplete')
    if context['passed_class'] != 'motor_vehicle':
        raise ValueError('Passed actor is not sourced as a motor vehicle')
    dimensions = {name: context[name + '_dimensions_m'] for name in ('rider', 'motor')}
    if any(len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in value)
           for value in dimensions.values()):
        raise ValueError('Original participant dimensions incomplete')
    occupants = context.get('motor_occupant_count')
    if type(occupants) is not int or occupants < 1:
        raise ValueError('Motor occupant count source incomplete')
    rows = [json.loads(line) for line in pose_path.read_text().splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError('Complete 600-frame 30-second pass interval required')
    first_rider = rectangle(rows[0]['rider_xy_m'], dimensions['rider'])
    first_motor = rectangle(rows[0]['motor_xy_m'], dimensions['motor'])
    initial_longitudinal_gap = max(first_motor[0] - first_rider[1], 0)
    first_behind = pass_start = pass_clear = None
    min_gap = math.inf
    min_gap_frame = None
    initial_closing_speed = None
    previous = None
    previous_native_frame = -1
    side = None
    for index, row in enumerate(rows):
        if electric:
            drive = row.get('drivetrain_command')
            if not isinstance(drive, dict) or not all(k in drive for k in
                    ('pedaling', 'pedal_cadence_rpm', 'assist_power_watts',
                     'speed_mps', 'assist_cutoff_mps', 'power_source')):
                raise ValueError('Electric-bicycle original drivetrain command absent')
            watts = drive['assist_power_watts']
            if (type(watts) not in (int, float) or not math.isfinite(watts) or
                watts < 0 or watts > qualification['motor_rated_watts'] or
                (watts > 0 and (drive['pedaling'] is not True or
                                drive['pedal_cadence_rpm'] <= 0)) or
                (watts > 0 and drive['speed_mps'] >= drive['assist_cutoff_mps']) or
                abs(drive['assist_cutoff_mps'] - 20 * .44704) > 1e-6):
                raise ValueError('Electric-bicycle Class 1 assist limit violated')
        native_frame = row.get('native_frame')
        if (type(native_frame) is not int or native_frame <= previous_native_frame or
                row.get('video_frame', index) != index or
                abs(row.get('time_s', -1) - index / 20) > 1e-5):
            raise ValueError('Original Native frame/time join differs')
        previous_native_frame = native_frame
        for name in ('rider_xy_m', 'motor_xy_m'):
            value = row.get(name)
            if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
                raise ValueError('Original participant pose incomplete: ' + name)
        rider = rectangle(row['rider_xy_m'], dimensions['rider'])
        motor = rectangle(row['motor_xy_m'], dimensions['motor'])
        if rider[1] < motor[0] and first_behind is None:
            first_behind = index
        if first_behind is not None and pass_start is None and rider[1] >= motor[0]:
            pass_start = index
            side = 'left' if row['rider_xy_m'][1] > row['motor_xy_m'][1] else 'right'
        if pass_start is not None and pass_clear is None:
            gap = surface_gap(rider, motor)
            if gap < min_gap:
                min_gap, min_gap_frame = gap, index
            if rider[0] > motor[1]:
                pass_clear = index
        if previous is not None and initial_closing_speed is None:
            rider_speed = (row['rider_xy_m'][0] - previous['rider_xy_m'][0]) * 20
            motor_speed = (row['motor_xy_m'][0] - previous['motor_xy_m'][0]) * 20
            initial_closing_speed = rider_speed - motor_speed
        previous = row
    if first_behind is None or pass_start is None or pass_clear is None:
        raise ValueError('Original capture does not show complete behind-to-clear-ahead pass')
    if not first_behind < pass_start < pass_clear:
        raise ValueError('Pass event order invalid')
    initial_ttc = (initial_longitudinal_gap / initial_closing_speed
                   if initial_closing_speed is not None and initial_closing_speed > 0 else None)
    return {'format': 'c146108-original-pass-measurement-v1',
            'frames': 600, 'rate_hz': 20,
            'source_sha256': {'pass-context.json': sha(context_path),
                              'participant-poses.jsonl': sha(pose_path)},
            'first_behind_frame': first_behind, 'pass_start_frame': pass_start,
            'pass_clear_frame': pass_clear, 'passing_side': side,
            'minimum_surface_gap_m': min_gap, 'minimum_surface_gap_frame': min_gap_frame,
            'initial_longitudinal_closing_speed_mps': initial_closing_speed,
            'initial_time_to_rear_overlap_s': initial_ttc,
            'motor_occupant_count_sourced': occupants,
            'electric_bicycle_controller_source_checked': electric,
            'endangerment_judgment': 'unreviewed', 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False,
            'limitations': ['Safety and endangerment have no source-backed numeric threshold',
                            'Axis-aligned synthetic bodies are a CPU measurement proxy',
                            'Original Native object classes, occupants and evasive responses require review']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain original measurement; use a fresh output')
    result = measure(args.attempt)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'pass_start_frame': result['pass_start_frame'],
                      'pass_clear_frame': result['pass_clear_frame'],
                      'minimum_surface_gap_m': result['minimum_surface_gap_m'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
