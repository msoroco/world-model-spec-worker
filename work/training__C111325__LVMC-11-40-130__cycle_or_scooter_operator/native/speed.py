"""Authored bicycle speed requests and source-only kinematic measurements.

This is a CPU fixture, not observed CARLA velocity or a prudence finding.
"""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
HZ = 20
START_X = -50.0
STOP_X = -2.0
MAX_SPEED = {'condition_a': 3.0, 'condition_b': 5.0}
CONTEXT_ID = 'c111325-stop-approach-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested(condition):
    if condition not in MAX_SPEED:
        raise ValueError('Unknown speed condition')
    x = START_X
    rows = []
    for frame in range(FRAMES):
        if frame:
            gap = max(0.0, STOP_X - x)
            speed = min(MAX_SPEED[condition], math.sqrt(3.0 * gap))
            x = min(STOP_X, x + speed / HZ)
            if STOP_X - x < 0.01:
                x = STOP_X
        rows.append({'frame': frame, 'time_s': frame / HZ,
                     'bicycle_center_xy_m': [round(x, 6), 0.0],
                     'context_id': CONTEXT_ID, 'stop_line_x_m': 0.0,
                     'requested_speed_condition': condition,
                     'source_kind': 'synthetic_scene_request',
                     'original_native_observed': False,
                     'legal_verdict': None})
    return rows


def measure(path, context_path):
    path, context_path = Path(path), Path(context_path)
    context = json.loads(context_path.read_text())
    if (context.get('context_id') != CONTEXT_ID or
            context.get('control') != 'stop_sign' or
            context.get('actor_requested') != 'bicycle' or
            context.get('stop_line_x_m') != 0.0 or
            context.get('visibility_m') != 75.0 or
            context.get('wet_road') is not False or
            context.get('crossing_pedestrian_present') is not False or
            context.get('physical_conditions_verified') is not False):
        raise ValueError('Untrusted speed context')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Expected 600 source frames')
    speeds = []
    prior = None
    conditions = set()
    for frame, row in enumerate(rows):
        point = row.get('bicycle_center_xy_m')
        if (row.get('frame') != frame or row.get('time_s') != frame / HZ or
                row.get('context_id') != CONTEXT_ID or
                row.get('stop_line_x_m') != 0.0 or
                row.get('source_kind') != 'synthetic_scene_request' or
                row.get('original_native_observed') is not False or
                row.get('legal_verdict') is not None or
                row.get('requested_speed_condition') not in MAX_SPEED or
                not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
            raise ValueError('Invalid bicycle source row')
        x, y = point
        if y != 0.0 or x > STOP_X or (prior is not None and x < prior):
            raise ValueError('Bicycle lane or stop geometry changed')
        if prior is not None:
            speed = (x - prior) * HZ
            if speed > 5.01:
                raise ValueError('Bicycle frame jump')
            speeds.append(speed)
        prior = x
        conditions.add(row['requested_speed_condition'])
    if len(conditions) != 1:
        raise ValueError('Mixed speed conditions')
    condition = next(iter(conditions))
    if rows != requested(condition):
        raise ValueError('Authored speed request changed')
    if rows[0]['bicycle_center_xy_m'][0] != START_X or rows[-1]['bicycle_center_xy_m'][0] != STOP_X:
        raise ValueError('Incomplete stop approach')
    stopped = next(i for i, row in enumerate(rows) if row['bicycle_center_xy_m'][0] == STOP_X)
    return {'format': 'c111325-source-speed-measurement-v1',
            'condition': condition, 'frames': FRAMES, 'rate_hz': HZ, 'duration_s': 30,
            'source_sha256': sha(path), 'context_sha256': sha(context_path),
            'first_stopped_frame': stopped,
            'peak_position_derived_speed_mps': round(max(speeds), 6),
            'distance_traveled_m': STOP_X - START_X,
            'stop_line_clearance_m': 2.0,
            'original_native_observed': False,
            'physical_conditions_verified': False,
            'prudence_verdict_claimed': False}
