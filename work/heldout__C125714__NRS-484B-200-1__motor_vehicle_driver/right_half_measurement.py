"""Measure complete body occupancy against an original directed centerline.

The statute's sufficient-width condition and listed exceptions require
separate evidence. This module returns geometry without legal classification.
"""

from hashlib import sha256
import json
from math import hypot
from pathlib import Path


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing original ' + label)
    return float(value[0]), float(value[1])


def _direction(value):
    x, y = _point(value, 'travel tangent')
    norm = hypot(x, y)
    if norm < 1e-6:
        raise ValueError('Degenerate travel direction')
    return x / norm, y / norm


def measure(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: directed_roadway_footprints.jsonl')
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Empty original roadway footprint source')
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original roadway footprint source') from error
    if len(rows) < 2:
        raise ValueError('Roadway occupancy needs multiple original frames')
    identity = rows[0].get('ego_id')
    if not identity:
        raise ValueError('Roadway occupancy lacks subject identity')
    observations = []
    previous = None
    for row in rows:
        if row.get('ego_id') != identity:
            raise ValueError('Roadway subject identity changed')
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError('Original frame/time identity missing')
        if previous is not None and (frame <= previous[0] or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original roadway frames are not joined at 20 Hz')
        previous = frame, time_s
        centre = _point(row.get('roadway_center_point_xy'), 'roadway center point')
        tx, ty = _direction(row.get('travel_tangent_xy'))
        right = -ty, tx
        corners = row.get('ego_corners')
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError('Original vehicle body needs four corners')
        def offset(value):
            x, y = _point(value, 'roadway/body point')
            return (x - centre[0]) * right[0] + (y - centre[1]) * right[1]
        edge_left = offset(row.get('left_road_edge_xy'))
        edge_right = offset(row.get('right_road_edge_xy'))
        if not edge_left < 0 < edge_right:
            raise ValueError('Directed roadway edges do not straddle centerline')
        lateral = [offset(corner) for corner in corners]
        observations.append({'frame': frame, 'time_s': time_s,
                             'body_min_right_offset_m': min(lateral),
                             'body_max_right_offset_m': max(lateral),
                             'body_entirely_right_half': min(lateral) >= 0,
                             'body_crosses_centerline': min(lateral) < 0 < max(lateral),
                             'measured_roadway_width_m': edge_right - edge_left,
                             'left_half_width_m': -edge_left,
                             'right_half_width_m': edge_right})
    return {'format': 'worker-directed-right-half-observation',
            'source_sha256': sha256(raw).hexdigest(), 'ego_id': identity,
            'frame_count': len(rows),
            'frames_entirely_right': [row['frame'] for row in observations if row['body_entirely_right_half']],
            'frames_crossing_centerline': [row['frame'] for row in observations if row['body_crosses_centerline']],
            'minimum_body_right_offset_m': min(row['body_min_right_offset_m'] for row in observations),
            'minimum_roadway_width_m': min(row['measured_roadway_width_m'] for row in observations),
            'observations': observations,
            'sufficient_width_legal_judgment': None,
            'exception_legal_judgment': None}
