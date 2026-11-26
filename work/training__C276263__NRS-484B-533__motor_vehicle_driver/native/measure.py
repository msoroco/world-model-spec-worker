"""Fail-closed saved telemetry for all three unattended-graded-stand duties.

Reports observed state; does not define perceptibility, effective brake, or law.
"""
import hashlib
import json
import math
from pathlib import Path

SOURCES = ('vehicle-frames.jsonl', 'grade-readback.json',
           'occupancy-frames.jsonl', 'video_frames.jsonl')
FRAMES = 600
VIEWS = {'overview', 'curb', 'wheel', 'cabin'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(folder, expected_hashes, diagnostic=False):
    folder = Path(folder)
    if set(expected_hashes) != set(SOURCES):
        raise ValueError('Complete saved-source hash inventory required')
    if any(sha(folder / name) != expected_hashes[name] for name in SOURCES):
        raise ValueError('Saved source hash differs')
    grade = json.loads((folder / SOURCES[1]).read_text())
    if (grade.get('format') != 'c276263-grade-readback-v1' or
            grade.get('source_kind') != ('synthetic_cpu' if diagnostic else 'native_map') or
            not number(grade.get('slope_fraction')) or
            not number(grade.get('right_curb_y_m')) or
            grade.get('road_id') != 1):
        raise ValueError('Grade or curb source differs')
    vehicle = [json.loads(s) for s in (folder / SOURCES[0]).read_text().splitlines()]
    occupancy = [json.loads(s) for s in (folder / SOURCES[2]).read_text().splitlines()]
    video = [json.loads(s) for s in (folder / SOURCES[3]).read_text().splitlines()]
    if not all(len(rows) == FRAMES for rows in (vehicle, occupancy, video)):
        raise ValueError('Complete 30-second source window required')
    actor_id = None
    instrument_id = None
    responsible_person_id = None
    unattended = []
    engine_states, brake_states, wheel_angles, movement = [], [], [], []
    for i, (v, o, f) in enumerate(zip(vehicle, occupancy, video)):
        if (v.get('frame') != i or o.get('frame') != i or f.get('video_frame') != i or
                v.get('native_frame') != o.get('native_frame') or
                v.get('native_frame') != f.get('native_frame') or
                f.get('carla_frame') != f.get('native_frame') or
                not all(number(row.get('time_s')) and abs(row['time_s'] - i/20) < .003
                        for row in (v, o, f))):
            raise ValueError('Original frame/time join differs')
        if v.get('source_kind') != ('synthetic_native_sample' if diagnostic else 'native_actor'):
            raise ValueError('Vehicle provenance differs')
        if o.get('source_kind') != ('synthetic_cpu' if diagnostic else 'occupancy_sensor'):
            raise ValueError('Occupancy provenance differs')
        if actor_id is None:
            actor_id = v.get('actor_id')
        if not isinstance(actor_id, int) or v.get('actor_id') != actor_id:
            raise ValueError('Vehicle identity differs')
        hashes = f.get('camera_raw_sha256')
        if not isinstance(hashes, dict) or set(hashes) != VIEWS or any(
                not isinstance(x, str) or len(x) != 64 for x in hashes.values()):
            raise ValueError('Four original camera hashes absent')
        if (type(o.get('occupant_count')) is not int or o['occupant_count'] < 0 or
                type(o.get('responsible_person_outside')) is not bool):
            raise ValueError('Unattended source observations absent')
        if v.get('engine_source') != ('synthetic_instrument' if diagnostic else 'instrumented_engine_sensor'):
            raise ValueError('Instrumented engine state absent')
        if v.get('wheel_source') != ('synthetic_instrument' if diagnostic else 'instrumented_front_wheel_sensor'):
            raise ValueError('Instrumented front-wheel state absent')
        if v.get('brake_source') != ('synthetic_instrument' if diagnostic else 'native_control_readback'):
            raise ValueError('Parking-brake readback absent')
        if not diagnostic:
            if instrument_id is None:
                instrument_id = v.get('instrument_id')
                responsible_person_id = o.get('responsible_person_id')
            if (not isinstance(instrument_id, str) or not instrument_id or
                    v.get('instrument_id') != instrument_id or
                    o.get('instrument_id') != instrument_id or
                    not isinstance(responsible_person_id, str) or not responsible_person_id or
                    o.get('responsible_person_id') != responsible_person_id or
                    not isinstance(v.get('engine_method'), str) or
                    v['engine_method'] in ('command', 'requested_control', 'speed_proxy') or
                    not isinstance(v.get('wheel_calibration_id'), str) or
                    not v['wheel_calibration_id'] or
                    not isinstance(o.get('attendance_method'), str) or
                    o['attendance_method'] in ('case_label', 'empty_render', 'requested_control')):
                raise ValueError('Original instrument method or identity differs')
            native_wheels = v.get('front_wheel_angles_native_deg')
            if (not isinstance(native_wheels, dict) or
                    set(native_wheels) != {'front_left', 'front_right'} or
                    not all(number(x) for x in native_wheels.values())):
                raise ValueError('Original front-wheel API observations absent')
        if (type(v.get('engine_running')) is not bool or
                type(v.get('parking_brake_set')) is not bool or
                not number(v.get('front_wheel_heading_to_curb_deg')) or
                not number(v.get('speed_mps')) or not number(v.get('position_x_m'))):
            raise ValueError('Complete three-duty telemetry absent')
        if o['occupant_count'] == 0 and o['responsible_person_outside']:
            unattended.append(i)
            engine_states.append(v['engine_running'])
            brake_states.append(v['parking_brake_set'])
            wheel_angles.append(v['front_wheel_heading_to_curb_deg'])
            movement.append(v['speed_mps'])
    if not unattended:
        raise ValueError('No source-observed unattended interval')
    return {'format': 'c276263-three-duty-measurement-v1',
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_native',
            'frames': FRAMES, 'rate_hz': 20, 'unattended_frames': unattended,
            'engine_running_any': any(engine_states),
            'parking_brake_unset_any': not all(brake_states),
            'front_wheel_heading_to_curb_deg_range': [min(wheel_angles), max(wheel_angles)],
            'speed_mps_max_during_unattended': max(movement),
            'grade_slope_fraction': grade['slope_fraction'],
            'right_curb_y_m': grade['right_curb_y_m'],
            'source_hashes': expected_hashes, 'perceptibility_reviewed': False,
            'effective_brake_reviewed': False, 'wheel_direction_reviewed': False,
            'legal_verdict': None}
