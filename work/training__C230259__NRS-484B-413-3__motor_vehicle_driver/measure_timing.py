"""Measure the requested stop and rear signal ordering from source-shaped rows.

The result describes physical observations and never decides legal appropriateness.
Original Native rows must come from capture; synthetic rows are diagnostic only.
"""
import hashlib
import json
import math
from pathlib import Path

RATE_HZ = 20
FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(root, expected_case, *, source_kind='synthetic_cpu'):
    root = Path(root)
    if source_kind not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Unsupported source kind')
    actors_path = root / 'actor-sources.jsonl'
    frames_path = root / 'camera-frames.jsonl'
    actors = _rows(actors_path)
    images = _rows(frames_path)
    if len(actors) != FRAMES or [r.get('frame') for r in actors] != list(range(FRAMES)):
        raise ValueError('Missing or nonconsecutive actor source frames')
    if len(images) != FRAMES * len(CAMERAS):
        raise ValueError('Missing camera source frames')
    indexed = {(r.get('frame'), r.get('camera')): r for r in images}
    if len(indexed) != len(images):
        raise ValueError('Duplicate camera source frame')
    for frame in range(FRAMES):
        for camera in CAMERAS:
            row = indexed.get((frame, camera))
            if row is None or not isinstance(row.get('rgb_sha256'), str) or len(row['rgb_sha256']) != 64:
                raise ValueError('Missing camera RGB source hash')
    for i, row in enumerate(actors):
        if row.get('case_id') != expected_case:
            raise ValueError('Case source mismatch')
        if abs(float(row.get('time_s', -1)) - i / RATE_HZ) > 1e-5:
            raise ValueError('Actor frame time mismatch')
        if row.get('rear_lane_id') != row.get('ego_lane_id'):
            raise ValueError('Rear vehicle leaves ego lane')
        if not row.get('rear_is_behind'):
            raise ValueError('Immediate rear relation absent')
        if float(row.get('surface_gap_m', -1)) <= 0:
            raise ValueError('Rear surface gap missing')
        if row.get('hand_signal') not in ('none', 'stop_or_slow'):
            raise ValueError('Hand signal source invalid')
        for key in ('ego_speed_mps', 'ego_accel_longitudinal_mps2'):
            if not math.isfinite(float(row[key])):
                raise ValueError('Nonfinite Native kinematics')
        if not isinstance(row.get('brake_lamp_observed'), bool):
            raise ValueError('Observed brake lamp state missing')
    lamp = next((r['frame'] for r in actors if r['brake_lamp_observed']), None)
    hand = next((r['frame'] for r in actors if r['hand_signal'] == 'stop_or_slow'), None)
    signal = min((x for x in (lamp, hand) if x is not None), default=None)
    stop = next((r['frame'] for r in actors if r['ego_speed_mps'] <= .1), None)
    decel = next((r['frame'] for r in actors if r['ego_accel_longitudinal_mps2'] <= -3), None)
    result = {
        'format': 'c230259-source-timing-measurement-v1',
        'case_id': expected_case,
        'source_kind': source_kind,
        'frames': FRAMES,
        'rate_hz': RATE_HZ,
        'first_observed_brake_lamp_frame': lamp,
        'first_observed_hand_signal_frame': hand,
        'first_observed_signal_frame': signal,
        'first_observed_stop_frame': stop,
        'first_diagnostic_3mps2_deceleration_frame': decel,
        'signal_precedes_stop': None if signal is None or stop is None else signal < stop,
        'signal_precedes_diagnostic_deceleration': None if signal is None or decel is None else signal < decel,
        'rear_same_lane_all_frames': True,
        'min_rear_surface_gap_m': min(float(r['surface_gap_m']) for r in actors),
        'source_sha256': {'actor-sources.jsonl': digest(actors_path),
                          'camera-frames.jsonl': digest(frames_path)},
        'fixed_motion_sha256': hashlib.sha256(json.dumps([
            (r['ego_speed_mps'], r['ego_accel_longitudinal_mps2'],
             r['ego_lane_id'], r['rear_lane_id'], r['rear_is_behind'],
             r['surface_gap_m']) for r in actors],
            separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        'diagnostic_deceleration_mps2': 3,
        'diagnostic_threshold_is_law': False,
        'legal_appropriateness': None,
        'original_native_observed': source_kind == 'original_native',
        'delivery_ready': False,
    }
    return result
