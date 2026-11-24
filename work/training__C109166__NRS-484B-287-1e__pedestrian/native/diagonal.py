"""Source-bound diagonal crossing timing; no physical or legal conclusion."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
DEVICE = 'c109166-diagonal-crossing-head'
START = (-6.0, -6.0)
END = (6.0, 6.0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def synthetic_rows(case):
    if case not in ('controlled_1', 'controlled_2'):
        raise ValueError('Unknown diagonal crossing case')
    result = []
    for frame in range(FRAMES):
        fraction = max(0, min(1, (frame - 100) / 240))
        x = START[0] + (END[0] - START[0]) * fraction
        y = START[1] + (END[1] - START[1]) * fraction
        state = ('diagonal_dont_walk' if case == 'controlled_2' and 100 <= frame < 160
                 else 'diagonal_walk')
        result.append({'frame': frame, 'time_s': frame / RATE_HZ,
                       'pedestrian_xy_m': [x, y],
                       'footprint_xy_m': [[x + dx, y + dy] for dx, dy in
                                          ((-.2, -.2), (-.2, .2), (.2, -.2), (.2, .2))],
                       'device_id': DEVICE, 'device_state': state,
                       'diagonal_movement_governed': True,
                       'source_kind': 'synthetic_scene_request'})
    return result


def measure(source_path, context_path):
    source_path, context_path = Path(source_path), Path(context_path)
    if not source_path.is_file() or not context_path.is_file():
        raise ValueError('Diagonal source or context missing')
    context = json.loads(context_path.read_text())
    if context.get('source_kind') != 'synthetic_scene_request':
        raise ValueError('Original diagonal device review is not present')
    if context.get('device_id') != DEVICE or context.get('governs_diagonal_movement') is not True:
        raise ValueError('Diagonal device governance unestablished')
    source = [json.loads(line) for line in source_path.read_text().splitlines() if line.strip()]
    if len(source) != FRAMES:
        raise ValueError('Full 600-frame diagonal source required')
    states = []
    previous = None
    path = 0.0
    for index, row in enumerate(source):
        if row.get('frame') != index or row.get('time_s') != index / RATE_HZ:
            raise ValueError('Diagonal frame/time join differs')
        if (row.get('device_id'), row.get('diagonal_movement_governed'), row.get('source_kind')) != (
            DEVICE, True, 'synthetic_scene_request'
        ):
            raise ValueError('Diagonal device/source identity differs')
        xy = row.get('pedestrian_xy_m')
        body = row.get('footprint_xy_m')
        if not isinstance(xy, list) or len(xy) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in xy):
            raise ValueError('Diagonal pedestrian position invalid')
        if not isinstance(body, list) or len(body) != 4 or any(not isinstance(p, list) or len(p) != 2 for p in body):
            raise ValueError('Diagonal full pedestrian footprint missing')
        if any(abs(sum(p[k] for p in body) / 4 - xy[k]) > 1e-8 for k in (0, 1)):
            raise ValueError('Diagonal pedestrian footprint/position differs')
        if abs(xy[0] - xy[1]) > .05:
            raise ValueError('Pedestrian left controlled diagonal corridor')
        if previous is not None:
            path += math.dist(previous, xy)
        previous = xy
        if row.get('device_state') not in ('diagonal_walk', 'diagonal_dont_walk'):
            raise ValueError('Diagonal device state invalid')
        if 100 <= index < 340:
            states.append((index, row['device_state']))
    if source[100]['pedestrian_xy_m'] != list(START) or source[340]['pedestrian_xy_m'] != list(END):
        raise ValueError('Diagonal crossing endpoints differ')
    if not 16.9 < path < 17.1:
        raise ValueError('Diagonal crossing path length differs')
    denied = [frame for frame, state in states if state == 'diagonal_dont_walk']
    return {'format': 'c109166-diagonal-timing-measurement-v1',
            'frames': FRAMES, 'duration_s': FRAMES / RATE_HZ,
            'crossing_frames': [100, 340], 'crossing_path_length_m': round(path, 6),
            'first_entry_device_state': source[100]['device_state'],
            'denied_during_crossing_frames': len(denied),
            'first_denied_frame': denied[0] if denied else None,
            'source_sha256': {source_path.name: sha(source_path), context_path.name: sha(context_path)},
            'governing_device_original_pixels_verified': False,
            'physical_crossing_observed': False, 'legal_verdict_claimed': False}
