"""Bind official-control captures to one Native junction and signal source.

This proves source identity for a future capture, not legal device status or
physical realization of the selected routes.
"""

import hashlib
import json
from math import isfinite


def _route(path, junction_id):
    if len(path) < 3 or path[0].is_junction or path[-1].is_junction:
        raise ValueError('Official route needs exterior and junction waypoints')
    rows = []
    for point in path:
        location = point.transform.location
        xy = [float(location.x), float(location.y)]
        if not all(map(isfinite, xy)):
            raise ValueError('Official route has nonfinite Native coordinates')
        actual = str(point.get_junction().id) if point.is_junction else None
        if actual is not None and actual != junction_id:
            raise ValueError('Official route crosses a different Native junction')
        rows.append({'road_id': int(point.road_id), 'lane_id': int(point.lane_id),
                     'junction_id': actual, 'xy': xy})
    if not any(row['junction_id'] == junction_id for row in rows):
        raise ValueError('Official route misses the selected junction')
    return rows


def bind_geometry(world_map, routes, selected_device):
    """Hash the selected original map, paths, and affected-lane device identity."""
    junction_id = str(routes['junction_id'])
    subject = _route(routes['subject'], junction_id)
    other = _route(routes['other'], junction_id)
    if (subject[0]['road_id'] == subject[-1]['road_id'] or
            other[0]['road_id'] != other[-1]['road_id'] or
            subject[0]['road_id'] == other[0]['road_id']):
        raise ValueError('Official T-junction Native continuity differs')
    light, signal_id, affected = selected_device
    if (not str(signal_id).strip() or
            (int(affected.road_id), int(affected.lane_id)) !=
            (subject[0]['road_id'], subject[0]['lane_id'])):
        raise ValueError('Official device does not govern bound ending lane')
    opendrive = world_map.to_opendrive()
    if not isinstance(opendrive, str) or not opendrive:
        raise ValueError('Official geometry lacks OpenDRIVE source')
    payload = {'format': 'worker-official-native-geometry',
               'map_name': world_map.name, 'junction_id': junction_id,
               'opendrive_sha256': hashlib.sha256(opendrive.encode()).hexdigest(),
               'routes': {'subject': subject, 'other': other},
               'governing_device': {'opendrive_signal_id': str(signal_id),
                                    'affected_road_id': int(affected.road_id),
                                    'affected_lane_id': int(affected.lane_id)},
               'legal_official_status_claimed': False}
    payload['geometry_sha256'] = _digest(payload)
    return payload


def _digest(payload):
    source = {key: value for key, value in payload.items()
              if key != 'geometry_sha256'}
    return hashlib.sha256(json.dumps(source, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require_expected_geometry(actual, expected):
    if (not isinstance(expected, dict) or
            expected.get('format') != 'worker-official-native-geometry' or
            expected.get('geometry_sha256') != _digest(expected)):
        raise ValueError('Expected official Native geometry binding is missing or stale')
    if actual['geometry_sha256'] != expected['geometry_sha256']:
        raise ValueError('Selected official Native geometry differs from expected binding')
    return actual
