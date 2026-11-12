"""CARLA-lazy placement of sourced turn-course indicators in a junction.

The source record documents claimed authorization. Placement and the Native
readback establish only physical construction, never municipal authority.
"""

from hashlib import sha256
import json
from pathlib import Path


def _xy(location):
    return [float(location.x), float(location.y)]


def place_markers(world, source_path, expected_sha256, make_transform):
    """Spawn and read back every indicated marker; caller owns returned actors.

    `make_transform(x, y, z, yaw)` is supplied by the Native runner so this
    module can be imported and tested without importing CARLA.
    """
    source_path = Path(source_path)
    raw = source_path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Authorized marker source hash changed')
    record = json.loads(raw)
    if (not record.get('authority_document') or not record.get('intersection_id')
            or record.get('median_opening_with_intersecting_road') is not True):
        raise ValueError('Marker authority or intersection identity missing')
    markers = record.get('markers')
    if not isinstance(markers, list) or not markers:
        raise ValueError('No physical turn-course markers specified')
    library = world.get_blueprint_library()
    road_map = world.get_map()
    actors = []
    try:
        for item in markers:
            if not all(k in item for k in ('x', 'y', 'z', 'yaw', 'blueprint_id')):
                raise ValueError('Marker placement incomplete')
            wp = road_map.get_waypoint(make_transform(item['x'], item['y'], item['z'], item['yaw']).location)
            if wp is None or not wp.is_junction:
                raise ValueError('Marker does not occupy a Native junction')
            blueprint = library.find(item['blueprint_id'])
            transform = make_transform(item['x'], item['y'], item['z'], item['yaw'])
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Native marker spawn failed')
            actors.append(actor)
            actual = _xy(actor.get_transform().location)
            if max(abs(actual[i] - float(item[k])) for i, k in enumerate(('x', 'y'))) > 0.05:
                raise ValueError('Native marker location readback differs')
        return {'actors': actors, 'source_sha256': expected_sha256,
                'intersection_id': record['intersection_id'],
                'physical_marker_xy_m': [_xy(a.get_transform().location) for a in actors]}
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise
