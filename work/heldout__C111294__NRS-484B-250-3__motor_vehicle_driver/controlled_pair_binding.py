"""Bind both highway-continuity captures to one measured Native route pair.

The binding records map and waypoint geometry, not legal highway identity. A
second capture can compare its selected Native paths to the first capture's
binding before any actors are spawned.
"""

import hashlib
import json
from math import isfinite


ROUTES = ('ending', 'continuing', 'other')


def _path_rows(path, junction_id):
    if len(path) < 3 or path[0].is_junction or path[-1].is_junction:
        raise ValueError('Controlled pair route lacks exterior and junction waypoints')
    rows = []
    for point in path:
        location = point.transform.location
        x, y = float(location.x), float(location.y)
        if not isfinite(x) or not isfinite(y):
            raise ValueError('Controlled pair contains nonfinite Native coordinates')
        actual_junction = str(point.get_junction().id) if point.is_junction else None
        if actual_junction is not None and actual_junction != junction_id:
            raise ValueError('Controlled pair crosses a different Native junction')
        rows.append({'road_id': int(point.road_id), 'lane_id': int(point.lane_id),
                     'junction_id': actual_junction, 'xy': [x, y]})
    if not any(row['junction_id'] == junction_id for row in rows):
        raise ValueError('Controlled pair route misses the selected junction')
    return rows


def bind_pair(pair):
    """Produce a stable key for the same three source routes on later runs."""
    if not isinstance(pair.get('map_name'), str) or not pair['map_name']:
        raise ValueError('Controlled pair lacks Native map identity')
    junction_id = pair.get('junction_id')
    if type(junction_id) not in (str, int) or str(junction_id) == '':
        raise ValueError('Controlled pair lacks Native junction identity')
    junction_id = str(junction_id)
    routes = {name: _path_rows(pair[name], junction_id) for name in ROUTES}
    if len({routes[name][0]['road_id'] for name in ROUTES}) != 3:
        raise ValueError('Controlled pair approach road identities conflict')
    if (routes['ending'][0]['road_id'] == routes['ending'][-1]['road_id'] or
            routes['continuing'][0]['road_id'] != routes['continuing'][-1]['road_id'] or
            routes['other'][0]['road_id'] != routes['other'][-1]['road_id']):
        raise ValueError('Controlled pair Native highway continuity differs')
    payload = {'format': 'worker-controlled-highway-route-pair',
               'map_name': pair['map_name'], 'junction_id': junction_id,
               'routes': routes, 'legal_highway_classification_claimed': False}
    if 'opendrive_sha256' in pair:
        digest = pair['opendrive_sha256']
        if not isinstance(digest, str) or len(digest) != 64 or any(
                character not in '0123456789abcdef' for character in digest):
            raise ValueError('Controlled pair OpenDRIVE source hash is invalid')
        payload['opendrive_sha256'] = digest
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode()
    payload['route_pair_sha256'] = hashlib.sha256(encoded).hexdigest()
    return payload


def require_same_pair(first, second):
    """Reject a later selection that changes either category or the fixed route."""
    a, b = bind_pair(first), bind_pair(second)
    if a['route_pair_sha256'] != b['route_pair_sha256']:
        changed = [name for name in ROUTES if a['routes'][name] != b['routes'][name]]
        if not changed:
            changed = ['map or junction']
        raise ValueError('Controlled Native route pair changed: ' + ', '.join(changed))
    return a


def require_expected_binding(pair, expected):
    """Check a retained binding before using a new Native route selection."""
    actual = bind_pair(pair)
    if not isinstance(expected, dict) or expected.get('format') != actual['format']:
        raise ValueError('Expected controlled route-pair binding is missing')
    expected_payload = {key: value for key, value in expected.items()
                        if key != 'route_pair_sha256'}
    encoded = json.dumps(expected_payload, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest() != expected.get('route_pair_sha256'):
        raise ValueError('Expected controlled route-pair binding hash is stale')
    if expected['route_pair_sha256'] != actual['route_pair_sha256']:
        raise ValueError('Selected Native route pair differs from expected binding')
    return actual
