"""Source-bound motion and exposure observations for NRS 484B.600(1)(b).

Closing time and gap are engineering observations, never an endangerment cutoff.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import Polygon


def _xy(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing original ' + label)
    pair = float(value[0]), float(value[1])
    if not all(isfinite(part) for part in pair):
        raise ValueError('Nonfinite original ' + label)
    return pair


def _polygon(value, label):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Original ' + label + ' needs four body corners')
    shape = Polygon([_xy(point, label) for point in value])
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('Degenerate original ' + label)
    return shape


def measure(path):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: exposed_actor_footprints.jsonl')
    raw = path.read_bytes()
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original exposure source') from error
    if len(rows) < 2:
        raise ValueError('Exposure requires multiple original frames')
    subject = rows[0].get('ego_id')
    exposed = rows[0].get('exposed_id')
    if not subject or not exposed or subject == exposed:
        raise ValueError('Original subject/exposed identities missing')
    observations = []
    previous = None
    for row in rows:
        if row.get('ego_id') != subject or row.get('exposed_id') != exposed:
            raise ValueError('Original exposure identity changed')
        if row.get('exposed_kind') not in ('pedestrian', 'cyclist', 'motor_vehicle', 'property'):
            raise ValueError('Exposed participant/property kind missing')
        frame, time_s = row.get('frame'), row.get('time_s')
        if (type(frame) is not int or type(time_s) not in (int, float)
                or not isfinite(time_s)):
            raise ValueError('Original frame/time identity missing')
        if previous and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original exposure frames are not joined at 20 Hz')
        previous = frame, time_s
        ego = _polygon(row.get('ego_corners_xy'), 'subject footprint')
        other = _polygon(row.get('exposed_corners_xy'), 'exposed footprint')
        ego_velocity = _xy(row.get('ego_velocity_xy_mps'), 'subject velocity')
        other_velocity = _xy(row.get('exposed_velocity_xy_mps'), 'exposed velocity')
        cx, cy = other.centroid.x - ego.centroid.x, other.centroid.y - ego.centroid.y
        separation = hypot(cx, cy)
        if separation < 1e-6:
            closing = None
        else:
            closing = ((ego_velocity[0] - other_velocity[0]) * cx +
                       (ego_velocity[1] - other_velocity[1]) * cy) / separation
        gap = ego.distance(other)
        observations.append({'frame': frame, 'time_s': time_s,
                             'ego_speed_mps': hypot(*ego_velocity),
                             'surface_gap_m': gap,
                             'contact': ego.intersects(other),
                             'radial_closing_speed_mps': closing,
                             'radial_gap_closing_time_s': gap / closing if closing and closing > 0 else None,
                             'exposed_kind': row.get('exposed_kind')})
    return {'format': 'worker-exposure-observation',
            'source_sha256': sha256(raw).hexdigest(),
            'ego_id': subject, 'exposed_id': exposed,
            'observations': observations,
            'minimum_surface_gap_m': min(item['surface_gap_m'] for item in observations),
            'maximum_ego_speed_mps': max(item['ego_speed_mps'] for item in observations),
            'any_contact': any(item['contact'] for item in observations),
            'endangerment_legal_judgment': None,
            'stopping_distance_legal_judgment': None}
