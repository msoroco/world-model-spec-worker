"""Snapshot source actors near the ego without inferring legal absence.

This is a capture component. A missing actor in this radius is only a scoped
observation; it cannot establish that no relevant hazard or control existed.
"""
from math import hypot, isfinite


def capture(world, ego, *, radius_m=100.0):
    if type(radius_m) not in (int, float) or not isfinite(radius_m) or radius_m <= 0:
        raise ValueError('Scene inventory needs a finite positive radius')
    origin = ego.get_transform().location
    actors = world.get_actors()
    if actors is None:
        raise ValueError('Native actor inventory unavailable')
    rows = []
    seen = set()
    for actor in actors:
        kind = getattr(actor, 'type_id', None)
        if not isinstance(kind, str) or not (
                kind.startswith('vehicle.') or kind == 'traffic.traffic_light'):
            continue
        ident = getattr(actor, 'id', None)
        if type(ident) is not int or ident in seen:
            raise ValueError('Native actor inventory has missing/duplicate identity')
        seen.add(ident)
        position = actor.get_transform().location
        values = (position.x, position.y, position.z)
        if any(type(value) not in (int, float) or not isfinite(value)
               for value in values):
            raise ValueError('Native actor inventory has invalid position')
        distance = hypot(position.x-origin.x, position.y-origin.y)
        if distance > radius_m:
            continue
        row = {'actor_id': ident, 'type_id': kind,
               'position_xyz_m': list(values), 'ego_distance_xy_m': distance}
        if kind == 'traffic.traffic_light':
            row['state'] = str(actor.get_state())
        rows.append(row)
    rows.sort(key=lambda item: item['actor_id'])
    return {'format': 'c179480-native-scene-inventory-v1',
            'source_kind': 'original_carla_actor_and_map_readback',
            'coverage': {'center': 'ego_actor_location', 'radius_m': radius_m,
                         'actor_classes': ['vehicle.*', 'traffic.traffic_light']},
            'actors': rows,
            'interpretation': 'scoped source snapshot only; no legal or physical absence claim'}
