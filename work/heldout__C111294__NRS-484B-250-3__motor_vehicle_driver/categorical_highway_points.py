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
