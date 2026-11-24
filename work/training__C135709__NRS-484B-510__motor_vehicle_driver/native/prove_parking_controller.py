"""Four controlled 600-frame motion/source diagnostics for NRS 484B.510."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from parking_controller import ParkingPlan, command
from restricted_zone_measure import CAMERAS, FRAME_COUNT, derive


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = (
    ('witness_1', 'taxi_pickup', False, False),
    ('witness_2', 'private_errand', False, False),
    ('exception_1_1', 'passenger_pickup', True, False),
    ('exception_1_2', 'passenger_pickup', True, True),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_frames(plan):
    x, speed = -25.0, 0.0
    rows, controls = [], []
    for index in range(FRAME_COUNT):
        control = command(plan, x, speed)
        controls.append(control)
        speed = max(0.0, min(plan.max_speed_mps,
                             speed + (2.5 * control['throttle'] -
                                      3.5 * control['brake']) / 20))
        x += speed / 20
        rows.append((x, speed))
    return rows, controls


def write_case(folder, suffix, purpose, loading, waiting, motion):
    folder.mkdir()
    positions, controls = motion
    zone = {'source_kind': 'synthetic_native_sample',
            'zone_bounds_m': [0, 0, 10, 4], 'sign_text': 'TAXI ONLY',
            'restricted_purpose': 'taxi_pickup',
            'subject_purpose_declaration': purpose, 'sign_authority': 'unverified'}
    frames = []
    for index, ((x, speed), control) in enumerate(zip(positions, controls)):
        frames.append({'frame': index, 'elapsed_s': index / 20,
                       'camera_ids': list(CAMERAS),
                       'ego_footprint_m': [x - 2, 1, x + 2, 3],
                       'ego_speed_mps': speed,
                       'door_open': loading and 310 <= index < 370,
                       'occupant_count': 2 if loading and index >= 340 else 1,
                       'pedestrian_count': 1 if loading and 310 <= index < 370 else 0,
                       'other_vehicle_waiting': waiting and 320 <= index < 420,
                       'other_vehicle_about_to_enter': False,
                       'controller_phase': control['phase'],
                       'controller_throttle': control['throttle'],
                       'controller_brake': control['brake']})
    (folder / 'zone.json').write_text(json.dumps(zone, sort_keys=True) + '\n')
    (folder / 'raw-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
    measured = derive(folder)
    if measured['stopped_in_zone_frames'] < 200:
        raise ValueError('Parking controller did not sustain an in-zone stop')
    if measured['waiting_or_entering_vehicle_frames_while_stopped'] != (100 if waiting else 0):
        raise ValueError('Waiting-vehicle contrast differs')
    if (measured['passenger_activity_frames_while_stopped'] > 0) != loading:
        raise ValueError('Passenger-activity contrast differs')
    return {'case_id': HERE.parent.name + '__' + suffix,
            'zone_sha256': sha(folder / 'zone.json'),
            'raw_frames_sha256': sha(folder / 'raw-frames.json'),
            'stopped_in_zone_frames': measured['stopped_in_zone_frames'],
            'passenger_activity_frames_while_stopped': measured['passenger_activity_frames_while_stopped'],
            'waiting_or_entering_vehicle_frames_while_stopped':
                measured['waiting_or_entering_vehicle_frames_while_stopped'],
            'declared_subject_purpose': measured['subject_purpose_declaration'],
            'subject_purpose_is_observed': False, 'sign_authority': 'unverified',
            'legal_conclusion': None}


def main():
    plan = ParkingPlan()
    motion = make_frames(plan)
    if not all(math.isfinite(x) and math.isfinite(speed) for x, speed in motion[0]):
        raise ValueError('Motion source contains nonfinite values')
    if any(x < -30 or x > 8 for x, _ in motion[0]):
        raise ValueError('Controlled parking trajectory escapes authored corridor')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c135709-parking-control-') as temp:
        rows = [write_case(Path(temp) / suffix, suffix, purpose, loading,
                           waiting, motion) for suffix, purpose, loading, waiting in CASES]
        if len({(row['zone_sha256'], row['raw_frames_sha256']) for row in rows}) != 4:
            raise ValueError('Four controlled source bundles are not distinct')
        if len({row['stopped_in_zone_frames'] for row in rows}) != 1:
            raise ValueError('Motion varied across legal-purpose comparison')
    for invalid in (ParkingPlan(target_center_x_m=10),
                    ParkingPlan(max_deceleration_mps2=0),
                    ParkingPlan(zone_x0_m=10, zone_x1_m=0)):
        try:
            invalid.validate()
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid geometry/controller accepted')
    try:
        command(plan, 0, float('nan'))
    except ValueError:
        pass
    else:
        raise AssertionError('Nonfinite speed accepted')
    return {'format': 'c135709-parking-controller-cpu-v1', 'passed': True,
            'frames_per_case': FRAME_COUNT, 'camera_identities_per_frame': len(CAMERAS),
            'cases': rows, 'invalid_plan_negatives': 3, 'nonfinite_state_negatives': 1,
            'physical_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
