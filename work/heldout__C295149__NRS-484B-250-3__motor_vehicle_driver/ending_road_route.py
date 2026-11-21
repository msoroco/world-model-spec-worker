"""Find connected ending-road and through-road approaches in a Native map."""

from collections import deque
from math import hypot

def _junction(waypoint):
    return str(waypoint.get_junction().id) if waypoint.is_junction else None


def _key(waypoint):
    location = waypoint.transform.location
    return waypoint.road_id, waypoint.lane_id, round(location.x, 1), round(location.y, 1)


def _paths_from_spawn(start, *, max_approach=120, max_junction=35):
    """Yield connected exterior -> junction -> exterior paths, including branches."""
    current = start
    approach = [start]
    seen = set()
    for _ in range(max_approach):
        if _key(current) in seen:
            return
        seen.add(_key(current))
        forward = current.next(2.0)
        if not forward:
            return
        entrances = [point for point in forward if point.is_junction]
        if entrances:
            break
        current = next((point for point in forward if point.road_id == current.road_id),
                       forward[0])
        approach.append(current)
    else:
        return
    pending = deque(((approach + [entrance], 0, _junction(entrance)) for entrance in entrances))
    while pending:
        path, depth, junction_id = pending.popleft()
        if depth > max_junction:
            continue
        for successor in path[-1].next(2.0):
            if _key(successor) in {_key(point) for point in path}:
                continue
            candidate = path + [successor]
            if successor.is_junction:
                if _junction(successor) == junction_id:
                    pending.append((candidate, depth + 1, junction_id))
            else:
                yield candidate


def select_t_routes(world_map, *, max_spawns=300, route_accept=None):
    """Select one same-junction pair; reject ambiguous non-T lane continuity."""
    routes = []
    for transform in world_map.get_spawn_points()[:max_spawns]:
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        for path in _paths_from_spawn(start):
            entrance = next(point for point in path if point.is_junction)
            exit_waypoint = path[-1]
            routes.append({'path': path,
                           'junction_id': _junction(entrance),
                           'approach_road_id': path[0].road_id,
                           'continues': path[0].road_id == exit_waypoint.road_id})
    # A selected turning branch cannot prove that a highway ends when another
    # connected branch of the same approach carries its road ID through.
    continuity = {(route['junction_id'], route['approach_road_id'])
                  for route in routes if route['continues']}
    for ending in routes:
        if (ending['junction_id'], ending['approach_road_id']) in continuity:
            continue
        for through in routes:
            if (not through['continues'] or
                    through['junction_id'] != ending['junction_id'] or
                    through['approach_road_id'] == ending['approach_road_id']):
                continue
            a = ending['path'][0].transform.get_forward_vector()
            b = through['path'][0].transform.get_forward_vector()
            length = hypot(a.x, a.y) * hypot(b.x, b.y)
            if length < 1e-6 or abs((a.x*b.x + a.y*b.y)/length) > .65:
                continue
            if route_accept is not None and not route_accept(ending, through):
                continue
            return {'subject': ending['path'], 'other': through['path'],
                    'junction_id': ending['junction_id'],
                    'map_name': world_map.name,
                    'selection_basis': 'connected Native 2 m lane successors, distinct OpenDRIVE road IDs and approximately transverse approaches',
                    'legal_highway_classification_claimed': False}
    raise ValueError('No connected ending-road/through-road T-junction approaches in Native map')
