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
