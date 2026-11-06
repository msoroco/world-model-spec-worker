"""Bounded Native waypoint traversal for a proposed left-turn lane link."""
import math


def survey(start, *, destination_road_id=4, destination_forward=(0.0, 1.0),
           step_m=1.0, max_waypoints=160):
    if start is None or not 0 < step_m <= 3 or max_waypoints < 1:
        raise ValueError('Invalid Native lane-link survey input')
    queue = [start]
    visited = set()
    while queue and len(visited) < max_waypoints:
        waypoint = queue.pop(0)
        identity = getattr(waypoint, 'id', None)
        if identity is None:
            raise ValueError('Native waypoint identity missing')
        if identity in visited:
            continue
        visited.add(identity)
        direction = waypoint.transform.get_forward_vector()
        norm = math.hypot(direction.x, direction.y)
        if norm < .99:
            raise ValueError('Native lane direction invalid')
        dot = (direction.x * destination_forward[0] +
               direction.y * destination_forward[1]) / norm
        if waypoint.road_id == destination_road_id and dot >= .98:
            return {'connected_lane_link': True,
                    'visited_waypoints': len(visited),
                    'destination_road_id': destination_road_id,
                    'source_kind': 'native_map_readback'}
        following = waypoint.next(step_m)
        if not isinstance(following, (list, tuple)):
            raise ValueError('Native waypoint successors invalid')
        queue.extend(following)
    return {'connected_lane_link': False,
            'visited_waypoints': len(visited),
            'destination_road_id': destination_road_id,
            'source_kind': 'native_map_readback'}


def full_body_destination_exit(rows, geometry):
    """Measure observed exit from saved body vertices, independent of entry."""
    point = geometry['destination_exit_point_native_m']
    direction = geometry['destination_forward_native']
    if len(point) != 2 or len(direction) != 2:
        raise ValueError('Invalid Native destination geometry')
    result = False
    for row in rows:
        vertices = row['native_body_xy_m']
        forward = row['native_forward_xy']
        if len(vertices) != 4 or len(forward) != 2:
            raise ValueError('Invalid Native body exit source')
        if (all(sum((v[i]-point[i])*direction[i] for i in range(2)) > 0
                for v in vertices) and
                sum(forward[i]*direction[i] for i in range(2)) >=
                math.cos(math.radians(20))):
            result = True
    return result
