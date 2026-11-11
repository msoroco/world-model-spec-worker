"""Find connected opposite approaches with an authored left-turn branch.

This selects geometry for the statutory exception; it does not decide whether
the vehicles legally approach each other or whether a turn was realized.
"""

from math import hypot

from ending_road_route import _paths_from_spawn, _junction


def _unit(waypoint):
    direction = waypoint.transform.get_forward_vector()
    norm = hypot(direction.x, direction.y)
    if norm < 1e-6:
        raise ValueError('Native route heading is unavailable')
    return direction.x / norm, direction.y / norm


def select_opposing_left_routes(world_map, *, max_spawns=300):
    paths = []
    for transform in world_map.get_spawn_points()[:max_spawns]:
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        for path in _paths_from_spawn(start):
            entrance = next((point for point in path if point.is_junction), None)
            if entrance is None:
                continue
            paths.append((path, _junction(entrance)))
    for turning, junction in paths:
        a = _unit(turning[0])
        exit_heading = _unit(turning[-1])
        left_cross = a[0] * exit_heading[1] - a[1] * exit_heading[0]
        if left_cross < .5:
            continue
        for opposite, other_junction in paths:
            if turning is opposite or junction != other_junction:
                continue
            b = _unit(opposite[0])
            if a[0] * b[0] + a[1] * b[1] > -.8:
                continue
            return {'turning': turning, 'opposite': opposite,
                    'junction_id': junction, 'map_name': world_map.name,
                    'selection_basis': 'connected Native lane successors, opposing entry headings and leftward exit heading',
                    'legal_exception_claimed': False}
    raise ValueError('No connected opposing left-turn routes at one Native junction')
