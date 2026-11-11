"""Select Native ending/continuing highway geometry comparison points."""

from math import hypot

from ending_road_route import _junction, _paths_from_spawn


def select_point(world_map, *, subject_continues, max_spawns=300):
    """Return one connected same-junction point with verified road continuity."""
    if type(subject_continues) is not bool:
        raise ValueError('Highway continuity choice must be boolean')
    routes = []
    for transform in world_map.get_spawn_points()[:max_spawns]:
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        for path in _paths_from_spawn(start):
            entrance = next((point for point in path if point.is_junction), None)
            if entrance is not None:
                routes.append({'path': path, 'junction_id': _junction(entrance),
                               'road_id': path[0].road_id,
                               'selected_exit_continues': path[0].road_id == path[-1].road_id})
    continuous = {(route['junction_id'], route['road_id']) for route in routes
                  if route['selected_exit_continues']}
    for subject in routes:
        source_continues = (subject['junction_id'], subject['road_id']) in continuous
        if source_continues != subject_continues:
            continue
        # A continuing *approach* can also have a turning exit. The selected
        # comparison route must itself carry the same road beyond the junction.
        if subject_continues and not subject['selected_exit_continues']:
            continue
        for other in routes:
            if (other['junction_id'], other['road_id']) not in continuous or (
                    subject['junction_id'] != other['junction_id'] or
                    subject['road_id'] == other['road_id']):
                continue
            a = subject['path'][0].transform.get_forward_vector()
            b = other['path'][0].transform.get_forward_vector()
            length = hypot(a.x, a.y) * hypot(b.x, b.y)
            if length < 1e-6 or abs((a.x*b.x + a.y*b.y)/length) > .65:
                continue
            return {'subject': subject['path'], 'other': other['path'],
                    'junction_id': subject['junction_id'], 'map_name': world_map.name,
                    'subject_highway_continues': source_continues,
                    'other_highway_continues': True,
                    'selection_basis': 'all connected Native 2 m lane successors and distinct road identities',
                    'legal_highway_status_claimed': False}
    raise ValueError('No connected Native highway-continuity category point')


def select_controlled_pair(world_map, *, max_spawns=300, route_accept=None):
    """Find both subject categories at one junction with the same through route.

    The selected through path is the identical waypoint sequence for both points.
    The callback can reject controlled or otherwise unsuitable approach pairs.
    """
    routes = []
    for transform in world_map.get_spawn_points()[:max_spawns]:
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        for path in _paths_from_spawn(start):
            entrance = next((point for point in path if point.is_junction), None)
            if entrance is not None:
                routes.append({'path': path, 'junction_id': _junction(entrance),
                               'road_id': path[0].road_id,
                               'continues': path[0].road_id == path[-1].road_id})
    continuous = {(r['junction_id'], r['road_id']) for r in routes if r['continues']}
    for other in routes:
        if not other['continues']:
            continue
        for ending in routes:
            if ((ending['junction_id'], ending['road_id']) in continuous or
                    ending['junction_id'] != other['junction_id'] or
                    ending['road_id'] == other['road_id']):
                continue
            for continuing in routes:
                if (not continuing['continues'] or
                        (continuing['junction_id'], continuing['road_id']) not in continuous or
                        continuing['junction_id'] != other['junction_id'] or
                        continuing['road_id'] in (other['road_id'], ending['road_id'])):
                    continue
                if not all(_transverse(r['path'][0], other['path'][0])
                           for r in (ending, continuing)):
                    continue
                if route_accept is not None and not all(
                        route_accept(r, other) for r in (ending, continuing)):
                    continue
                return {
                    'ending': ending['path'], 'continuing': continuing['path'],
                    'other': other['path'], 'junction_id': other['junction_id'],
                    'map_name': world_map.name,
                    'witness_paths': [route['path'] for route in routes
                                      if route['junction_id'] == other['junction_id'] and
                                      route['road_id'] in (ending['road_id'],
                                                           continuing['road_id'],
                                                           other['road_id'])],
                    'selection_basis': 'connected Native successors with one fixed through route',
                    'legal_highway_status_claimed': False,
                }
    raise ValueError('No controlled ending/continuing Native highway pair')


def _transverse(a, b):
    va = a.transform.get_forward_vector()
    vb = b.transform.get_forward_vector()
    length = hypot(va.x, va.y) * hypot(vb.x, vb.y)
    return length >= 1e-6 and abs((va.x * vb.x + va.y * vb.y) / length) <= .65
