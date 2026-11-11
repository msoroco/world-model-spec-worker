"""Original-frame vehicle body position relative to the highway's right half.

The road tangent is the map traffic direction, not the ego heading. Width and
exception context are observations; no legal width threshold is supplied here.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import Polygon


EXCEPTIONS = ('passing_same_direction', 'right_half_closed', 'three_lane_highway',
              'posted_one_way', 'insufficient_width')


def _source(path, label):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required original source: ' + label)
    raw = path.read_bytes()
    return raw, sha256(raw).hexdigest()


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing original ' + label)
    try:
        point = tuple(float(v) for v in value)
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid original ' + label) from error
    if not all(isfinite(v) for v in point):
        raise ValueError('Invalid original ' + label)
    return point


def measure(road_frames_path, context_path):
    raw, frame_sha = _source(road_frames_path, 'ego_road_frames.jsonl')
    context_raw, context_sha = _source(context_path, 'road_exception_context.json')
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
        context = json.loads(context_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original right-half source') from error
    if len(rows) < 2:
        raise ValueError('Right-half measurement needs multiple original frames')
    if not isinstance(context, dict):
        raise ValueError('Exception context must be an object')
    exceptions = {}
    for key in EXCEPTIONS:
        item = context.get(key)
        if not isinstance(item, dict) or 'value' not in item:
            raise ValueError('Missing separately reviewed exception: ' + key)
        value, source = item['value'], item.get('source_ref')
        if value is not None and (type(value) is not bool or not isinstance(source, str) or not source):
            raise ValueError('Known exception needs cited source: ' + key)
        if value is None and source is not None:
            raise ValueError('Unknown exception cannot cite a decided value: ' + key)
        exceptions[key] = {'value': value, 'source_ref': source}
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original right-half frame/time invalid')
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original right-half frames are not continuous at 20 Hz')
        previous = frame, time_s
        center = _point(row.get('road_center_xy'), 'road centre')
        tangent = _point(row.get('road_travel_tangent_xy'), 'traffic direction')
        norm = hypot(*tangent)
        if norm < 1e-6:
            raise ValueError('Original traffic direction is degenerate')
        corners = row.get('ego_corners_xy')
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError('Original ego footprint needs four corners')
        corners = [_point(v, 'ego footprint') for v in corners]
        polygon = Polygon(corners)
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError('Original ego footprint is degenerate')
        try:
            width = float(row['road_width_m'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Original highway width missing') from error
        if not isfinite(width) or width <= 0:
            raise ValueError('Original highway width invalid')
        lateral = [((tangent[0] * (point[1] - center[1]) -
                     tangent[1] * (point[0] - center[0])) / norm)
                   for point in corners]
        observations.append({
            'frame': frame, 'time_s': time_s,
            'road_id': row.get('road_id'), 'lane_id': row.get('lane_id'),
            'road_width_m': width,
            'minimum_signed_lateral_m': min(lateral),
            'maximum_signed_lateral_m': max(lateral),
            'whole_body_right_half': max(lateral) <= 0,
            'whole_body_left_half': min(lateral) >= 0,
            'body_crosses_centerline': min(lateral) < 0 < max(lateral),
        })
    return {'format': 'worker-right-half-observation',
            'sources': {'ego_road_frames.jsonl': frame_sha,
                        'road_exception_context.json': context_sha},
            'observations': observations, 'exception_context': exceptions,
            'sufficient_width_legal_judgment': None,
            'passing_law_legal_judgment': None,
            'right_half_legal_judgment': None}
