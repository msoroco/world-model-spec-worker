"""Construct candidate listener positions from a connected Native turn route.

This plans engineering distances. It makes no audibility or affected-party claim.
"""

import math


def listener_points(route, lateral_offsets_m=(2.0, 4.0, 6.0)):
    """Return three route-relative points and their closest sampled route distance.

    ``route`` is an ordered list of original Native waypoint (x, y) positions.
    The caller must separately verify route connectivity and spawnable sidewalks.
    """
    points = [tuple(map(float, point)) for point in route]
    if len(points) < 3 or any(len(point) != 2 or not all(map(math.isfinite, point))
                              for point in points):
        raise ValueError('Original Native turn route is missing or nonfinite')
    offsets = tuple(float(value) for value in lateral_offsets_m)
    if (len(offsets) != 3 or not all(math.isfinite(value) and value > 0 for value in offsets)
            or len(set(offsets)) != 3 or tuple(sorted(offsets)) != offsets):
        raise ValueError('Listener sweep needs three increasing positive offsets')
    centre = len(points) // 2
    before, anchor, after = points[centre - 1:centre + 2]
    dx, dy = after[0] - before[0], after[1] - before[1]
    span = math.hypot(dx, dy)
    if span < 0.25:
        raise ValueError('Native turn tangent is degenerate')
    nx, ny = -dy / span, dx / span
    result = []
    for offset in offsets:
        x, y = anchor[0] + offset * nx, anchor[1] + offset * ny
        nearest = min(math.hypot(x - px, y - py) for px, py in points)
        result.append({'point_x_m': x, 'point_y_m': y,
                       'route_lateral_offset_m': offset,
                       'nearest_sampled_route_m': nearest,
                       'anchor_index': centre})
    return result


def spawnable_listener_points(carla_map, carla, route, lateral_offsets_m=(2.0, 4.0, 6.0),
                              max_projection_m=0.75):
    """Resolve route-relative points to actual sidewalk waypoints before spawning.

    This is lazy with respect to CARLA and rejects a sweep point when the map
    cannot place a listener sufficiently close to the requested coordinate.
    Callers must still confirm the selected turn route and actual capture.
    """
    if not math.isfinite(max_projection_m) or max_projection_m < 0:
        raise ValueError('Invalid sidewalk projection tolerance')
    resolved = []
    for point in listener_points(route, lateral_offsets_m):
        waypoint = carla_map.get_waypoint(
            carla.Location(x=point['point_x_m'], y=point['point_y_m'], z=0.5),
            project_to_road=False, lane_type=carla.LaneType.Sidewalk)
        if waypoint is None:
            raise ValueError('Listener sweep point has no Native sidewalk waypoint')
        location = waypoint.transform.location
        displacement = math.hypot(location.x - point['point_x_m'],
                                  location.y - point['point_y_m'])
        if not math.isfinite(displacement) or displacement > max_projection_m:
            raise ValueError('Listener sweep sidewalk projection exceeds tolerance')
        resolved.append({**point, 'spawn_x_m': location.x, 'spawn_y_m': location.y,
                         'spawn_z_m': location.z,
                         'sidewalk_projection_m': displacement,
                         'lane_id': waypoint.lane_id,
                         'road_id': waypoint.road_id})
    if len({(row['spawn_x_m'], row['spawn_y_m']) for row in resolved}) != len(resolved):
        raise ValueError('Listener sweep points collapse to one Native spawn')
    return resolved
