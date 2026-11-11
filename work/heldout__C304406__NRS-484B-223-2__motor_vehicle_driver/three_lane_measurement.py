"""Original-frame occupancy of ordered three-lane highway geometry.

Map lane polygons and traffic direction are geometry sources. Clearly marked
lanes, posted allocation and safe passing distance require separate evidence.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import Polygon


CONDITIONS = ('three_clearly_marked_lanes', 'passing_same_direction',
              'highway_clearly_visible', 'center_clear_safe_distance',
              'preparing_left_turn', 'center_allocated_same_direction',
              'allocation_sign_posted')
LANES = ('right', 'center', 'extreme_left')


def _load(path, label):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + label)
    raw = path.read_bytes()
    try:
        value = json.loads(raw) if path.suffix == '.json' else [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + label) from error
    return value, sha256(raw).hexdigest()


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Original lane point missing')
    try:
        xy = tuple(float(v) for v in value)
    except (TypeError, ValueError) as error:
        raise ValueError('Original lane point invalid') from error
    if not all(isfinite(v) for v in xy):
        raise ValueError('Original lane point invalid')
    return xy


def _polygon(points, label):
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError('Original ' + label + ' polygon incomplete')
    shape = Polygon([_point(p) for p in points])
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('Original ' + label + ' polygon invalid')
    return shape


def measure(frame_path, context_path):
    rows, frame_sha = _load(frame_path, 'three_lane_frames.jsonl')
    context, context_sha = _load(context_path, 'three_lane_context.json')
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(context, dict):
        raise ValueError('Original three-lane sources incomplete')
    conditions = {}
    for name in CONDITIONS:
        item = context.get(name)
        if not isinstance(item, dict) or 'value' not in item:
            raise ValueError('Three-lane condition missing: ' + name)
        value, source = item['value'], item.get('source_ref')
        if value is not None and (type(value) is not bool or not isinstance(source, str) or not source):
            raise ValueError('Known three-lane condition needs source: ' + name)
        if value is None and source is not None:
            raise ValueError('Unknown three-lane condition cannot cite verdict: ' + name)
        conditions[name] = {'value': value, 'source_ref': source}
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original three-lane frame/time invalid')
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original three-lane frames are not joined at 20 Hz')
        previous = frame, time_s
        tangent = _point(row.get('road_travel_tangent_xy'))
        norm = hypot(*tangent)
        if norm < 1e-6:
            raise ValueError('Original three-lane travel direction degenerate')
        ego = _polygon(row.get('ego_corners_xy'), 'ego')
        lane_points = row.get('lane_polygons_xy')
        if not isinstance(lane_points, dict) or set(lane_points) != set(LANES):
            raise ValueError('Exactly three named original lane polygons required')
        lanes = {name: _polygon(lane_points[name], name) for name in LANES}
        def lateral(shape):
            c = shape.centroid
            return (tangent[0] * c.y - tangent[1] * c.x) / norm
        if not lateral(lanes['right']) < lateral(lanes['center']) < lateral(lanes['extreme_left']):
            raise ValueError('Original lane order differs from travel direction')
        fractions = {name: ego.intersection(shape).area / ego.area
                     for name, shape in lanes.items()}
        observations.append({'frame': frame, 'time_s': time_s,
                             'road_id': row.get('road_id'),
                             'body_lane_overlap_fraction': fractions,
                             'extreme_left_body_overlap': fractions['extreme_left'] > 0,
                             'center_body_overlap': fractions['center'] > 0})
    return {'format': 'worker-three-lane-observation',
            'sources': {'three_lane_frames.jsonl': frame_sha,
                        'three_lane_context.json': context_sha},
            'observations': observations, 'condition_context': conditions,
            'safe_distance_legal_judgment': None,
            'center_lane_exception_legal_judgment': None,
            'extreme_left_lane_legal_judgment': None}
