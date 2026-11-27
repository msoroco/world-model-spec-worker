"""Pure geometry for prospective Native rail survey and curb placement."""

import math

from rail_footprint_meter import _segment_distance


def rail_from_actor(actor):
    """Use the long horizontal bounding-box axis as a surveyed rail candidate."""
    box = actor.bounding_box
    pose = actor.get_transform()
    center = pose.transform(box.location)
    if box.extent.x >= box.extent.y:
        direction = pose.get_forward_vector()
        half_length, half_width = box.extent.x, box.extent.y
    else:
        direction = pose.get_right_vector()
        half_length, half_width = box.extent.y, box.extent.x
    if half_length < 2 or half_width > .5:
        raise ValueError('Native rail actor extent is not a narrow physical rail')
    dx, dy = float(direction.x), float(direction.y)
    norm = math.hypot(dx, dy)
    if norm < .99:
        raise ValueError('Native rail actor direction invalid')
    dx, dy = dx / norm, dy / norm
    return {'rail_id': str(actor.id), 'source_kind': 'native_survey',
            'source_ref': 'native-actor:' + str(actor.id) + ':type=' + actor.type_id + ':bounding_box',
            'polyline_xy_m': [[center.x - dx * half_length, center.y - dy * half_length],
                              [center.x + dx * half_length, center.y + dy * half_length]],
            'actor_type_id': actor.type_id, 'bbox_half_width_m': half_width,
            'physical_rail_identity_independently_reviewed': False}


def body_polygon(center, forward, half_length, half_width):
    fx, fy = forward
    norm = math.hypot(fx, fy)
    if norm < .99 or half_length <= 0 or half_width <= 0:
        raise ValueError('Invalid body geometry')
    fx, fy = fx / norm, fy / norm
    rx, ry = -fy, fx
    return [[center[0] + a * fx + b * rx, center[1] + a * fy + b * ry]
            for a, b in ((half_length, half_width), (half_length, -half_width),
                         (-half_length, -half_width), (-half_length, half_width))]


def nearest_gap(poly, rails):
    return min(_segment_distance(poly[i], poly[(i + 1) % 4], a, b)
               for i in range(4) for rail in rails
               for a, b in [rail['polyline_xy_m']])


def choose_curb_waypoint(waypoints, rails, target_gap_m, half_length, half_width):
    """Choose a measured geometry candidate; Native driveability remains to be proved."""
    if not rails or target_gap_m <= 0:
        raise ValueError('Rail survey or placement target missing')
    candidates = []
    for waypoint in waypoints:
        if getattr(waypoint, 'lane_id', 0) >= 0:
            continue
        right_lane = waypoint.get_right_lane()
        if right_lane is None or 'sidewalk' not in str(right_lane.lane_type).lower():
            continue
        right = waypoint.transform.get_right_vector()
        forward = waypoint.transform.get_forward_vector()
        shift = max(0., waypoint.lane_width / 2 - half_width - .25)
        center = [waypoint.transform.location.x + right.x * shift,
                  waypoint.transform.location.y + right.y * shift]
        poly = body_polygon(center, (forward.x, forward.y), half_length, half_width)
        gap = nearest_gap(poly, rails)
        candidates.append((abs(gap - target_gap_m), gap, waypoint, center))
    if not candidates:
        raise ValueError('No Native curbside driving waypoint near physical rails')
    candidates.sort(key=lambda row: row[0])
    error, gap, waypoint, center = candidates[0]
    if error > .75:
        raise ValueError('Native curb placement misses requested rail gap')
    return {'waypoint': waypoint, 'center_xy_m': center,
            'predicted_footprint_gap_m': gap,
            'placement_error_m': error,
            'physical_parking_observed': False}
