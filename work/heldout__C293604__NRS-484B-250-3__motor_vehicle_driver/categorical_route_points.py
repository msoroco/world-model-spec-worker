"""Select connected Native route points around the opposing-left exception.

These are geometric comparison points. Legal status requires later review.
"""

from ending_road_route import _junction, _paths_from_spawn
from opposing_left_route import _unit


def select_point(world_map, *, opposite, leftward, max_spawns=300):
    """Return an authored approach/exit category from original Native successors."""
    if type(opposite) is not bool or type(leftward) is not bool:
        raise ValueError('Categorical route choices must be booleans')
    paths = []
    for transform in world_map.get_spawn_points()[:max_spawns]:
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        for path in _paths_from_spawn(start):
            entrance = next((point for point in path if point.is_junction), None)
            if entrance is not None:
                paths.append((path, _junction(entrance)))
    for turning, junction in paths:
        a, exit_heading = _unit(turning[0]), _unit(turning[-1])
        cross = a[0] * exit_heading[1] - a[1] * exit_heading[0]
        forward = a[0] * exit_heading[0] + a[1] * exit_heading[1]
        if leftward:
            if cross < .5:
                continue
        elif abs(cross) > .2 or forward < .8:
            continue
        for other, other_junction in paths:
            if turning is other or junction != other_junction or turning[0] is other[0]:
                continue
            b = _unit(other[0])
            dot = a[0] * b[0] + a[1] * b[1]
            if (opposite and dot > -.8) or (not opposite and dot < .8):
                continue
            return {'turning': turning, 'other': other,
                    'junction_id': junction, 'map_name': world_map.name,
                    'opposite_approach': opposite, 'leftward_exit': leftward,
                    'approach_heading_dot': dot, 'exit_left_cross': cross,
                    'selection_basis': 'connected Native 2 m lane successors and source heading geometry',
                    'legal_exception_claimed': False}
    raise ValueError('No connected Native categorical route point at one junction')
