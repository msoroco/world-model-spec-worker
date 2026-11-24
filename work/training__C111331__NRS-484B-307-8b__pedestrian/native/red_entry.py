"""Synthetic steady-red pedestrian-entry source and measured footprint checks."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
HZ = 20
CONTEXT_ID = 'c111331-facing-red-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested(condition):
    if condition not in ('condition_a', 'condition_b'):
        raise ValueError('Unknown pedestrian entry condition')
    rows = []
    for frame in range(FRAMES):
        if condition == 'condition_a' or frame < 200:
            y = 3.2
        elif frame < 260:
            y = 3.2 - 4.2 * (frame - 200) / 60
        else:
            y = -1.0
        y = round(y, 6)
        feet = [[round(dx, 6), round(y + dy, 6)]
                for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))]
        rows.append({'frame': frame, 'time_s': frame / HZ,
                     'pedestrian_center_xy_m': [0.0, y],
                     'pedestrian_footprint_xy_m': feet,
                     'context_id': CONTEXT_ID, 'signal_id': 'head_ped_1',
                     'signal_state': 'steady_red_alone',
                     'other_device_id': None,
                     'other_device_permits': False,
                     'requested_entry_condition': condition,
                     'source_kind': 'synthetic_scene_request',
                     'original_native_observed': False,
                     'legal_verdict': None})
    return rows


def measure(source, context):
    source, context = Path(source), Path(context)
    scene = json.loads(context.read_text())
    if (scene.get('context_id') != CONTEXT_ID or
            scene.get('highway_y_max_m') != 2.0 or
            scene.get('signal_id') != 'head_ped_1' or
            scene.get('signal_location_xy_m') != [0.0, 5.0] or
            scene.get('signal_face_vector_xy') != [0.0, -1.0] or
            scene.get('pedestrian_approach_vector_xy') != [0.0, -1.0] or
            scene.get('signal_authority_native_verified') is not False or
            scene.get('other_device_authority_native_verified') is not False):
        raise ValueError('Untrusted signal geometry or authority')
    dot = sum(a*b for a,b in zip(scene['signal_face_vector_xy'],
                                 scene['pedestrian_approach_vector_xy']))
    if dot <= 0:
        raise ValueError('Signal does not face pedestrian approach')
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Expected 600 source frames')
    conditions = set()
    road_frames = []
    prior = None
    for frame, row in enumerate(rows):
        center, feet = row.get('pedestrian_center_xy_m'), row.get('pedestrian_footprint_xy_m')
        if (row.get('frame') != frame or row.get('time_s') != frame / HZ or
                row.get('context_id') != CONTEXT_ID or row.get('signal_id') != scene['signal_id'] or
                row.get('signal_state') != 'steady_red_alone' or
                row.get('other_device_id') is not None or
                row.get('other_device_permits') is not False or
                row.get('source_kind') != 'synthetic_scene_request' or
                row.get('original_native_observed') is not False or
                row.get('legal_verdict') is not None or
                row.get('requested_entry_condition') not in ('condition_a','condition_b') or
                not isinstance(center, list) or len(center) != 2 or
                not isinstance(feet, list) or len(feet) != 4):
            raise ValueError('Invalid red-signal source row')
        values = [*center, *(v for point in feet for v in point)]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError('Nonfinite pedestrian geometry')
        if any(len(point) != 2 for point in feet):
            raise ValueError('Invalid footprint')
        expected = [[round(center[0]+dx,6),round(center[1]+dy,6)]
                    for dx,dy in ((-.16,-.16),(-.16,.16),(.16,-.16),(.16,.16))]
        if feet != expected:
            raise ValueError('Footprint and center disagree')
        if prior is not None and math.dist(center, prior) > .08:
            raise ValueError('Pedestrian frame discontinuity')
        prior = center
        conditions.add(row['requested_entry_condition'])
        if min(point[1] for point in feet) < scene['highway_y_max_m']:
            road_frames.append(frame)
    if len(conditions) != 1:
        raise ValueError('Mixed entry conditions')
    condition = next(iter(conditions))
    if rows != requested(condition):
        raise ValueError('Authored entry request changed')
    if (condition == 'condition_a' and road_frames) or (condition == 'condition_b' and not road_frames):
        raise ValueError('Highway-entry contrast absent')
    return {'format': 'c111331-red-entry-source-measurement-v1',
            'condition': condition, 'frames': FRAMES, 'rate_hz': HZ, 'duration_s': 30,
            'signal_face_dot_approach': dot,
            'first_highway_footprint_frame': min(road_frames) if road_frames else None,
            'highway_footprint_frames': len(road_frames),
            'source_sha256': sha(source), 'context_sha256': sha(context),
            'signal_authority_native_verified': False,
            'other_device_authority_native_verified': False,
            'legal_verdict_claimed': False}
