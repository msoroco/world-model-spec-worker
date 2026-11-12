"""Retain Native road geometry separately from pavement surface review.

OpenDRIVE lane type and width provide a controller target. They do not decide
whether the target is off the paved portion of the highway under NRS 484B.210.
"""

from math import cos, pi, sin


def _right_axis(waypoint):
    yaw = float(waypoint.transform.rotation.yaw) * pi / 180
    return (sin(yaw), -cos(yaw))


def _edge(waypoint, axis):
    width = float(waypoint.lane_width)
    if width <= 0:
        raise ValueError('Native lane width is not positive')
    center = waypoint.transform.location
    return (float(center.x) + width / 2 * axis[0],
            float(center.y) + width / 2 * axis[1])


def mapped_right_edges(waypoint, beyond_m=1.5):
    """Return original driving and mapped road edges plus requested target.

    A right shoulder lane, if present, extends the mapped road edge. Pavement
    material and traversability need independent original video/Native review.
    """
    if beyond_m not in (1.5, 2.5):
        raise ValueError('Unsupported physical margin beyond mapped road edge')
    current = waypoint
    seen = set()
    while True:
        key = (int(current.road_id), int(current.lane_id))
        if key in seen:
            raise ValueError('Right driving topology loops')
        seen.add(key)
        right = current.get_right_lane()
        if (right is None or int(right.road_id) != int(current.road_id)
                or 'driving' not in str(right.lane_type).lower()):
            break
        current = right
    axis = _right_axis(current)
    driving_edge = _edge(current, axis)
    road_edge = driving_edge
    shoulder_id = None
    shoulder = current.get_right_lane()
    if (shoulder is not None and int(shoulder.road_id) == int(current.road_id)
            and 'shoulder' in str(shoulder.lane_type).lower()):
        shoulder_id = int(shoulder.lane_id)
        road_edge = _edge(shoulder, axis)
    return {'driving_edge_xy_m': driving_edge,
            'mapped_road_edge_xy_m': road_edge,
            'right_axis_xy': axis,
            'target_xy_m': (road_edge[0] + beyond_m * axis[0],
                            road_edge[1] + beyond_m * axis[1]),
            'driving_lane_id': int(current.lane_id),
            'shoulder_lane_id': shoulder_id,
            'road_id': int(current.road_id),
            'pavement_surface_review_required': True}


def signed_clearance(location, edge_xy, right_axis_xy):
    return ((float(location.x) - edge_xy[0]) * right_axis_xy[0]
            + (float(location.y) - edge_xy[1]) * right_axis_xy[1])
