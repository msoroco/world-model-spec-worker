"""Derive a directed two-lane road section from original Native waypoints.

This is an acquisition helper, not a legal width or exception classifier.
The mapped centerline must be supported by adjoining opposite-direction lanes.
"""

from math import hypot


def _xy(location):
    return [float(location.x), float(location.y)]


def _tangent(waypoint):
    vector = waypoint.transform.get_forward_vector()
    norm = hypot(vector.x, vector.y)
    if norm < 1e-6:
        raise ValueError('Mapped lane has degenerate travel tangent')
    return vector.x / norm, vector.y / norm


def directed_road_section(subject, opposite, *, join_tolerance_m=0.4):
    if subject is None or opposite is None:
        raise ValueError('Opposing mapped lane required for centerline')
    if subject.road_id != opposite.road_id:
        raise ValueError('Opposing lane is from another road')
    if subject.lane_id * opposite.lane_id >= 0:
        raise ValueError('Opposing lane IDs must have opposite signs')
    tx, ty = _tangent(subject)
    ox, oy = _tangent(opposite)
    if tx * ox + ty * oy > -0.95:
        raise ValueError('Opposing mapped lane travel direction differs')
    if not (subject.lane_width > 0 and opposite.lane_width > 0):
        raise ValueError('Mapped lane width missing')
    # CARLA map coordinates use +y to the driver's right when travelling +x.
    right = -ty, tx
    subject_xy = _xy(subject.transform.location)
    opposite_xy = _xy(opposite.transform.location)
    lateral = ((opposite_xy[0] - subject_xy[0]) * right[0] +
               (opposite_xy[1] - subject_xy[1]) * right[1])
    if lateral >= 0:
        raise ValueError('Opposing lane is not left of subject lane')
    subject_border = [subject_xy[i] - right[i] * subject.lane_width / 2 for i in (0, 1)]
    opposite_border = [opposite_xy[i] + right[i] * opposite.lane_width / 2 for i in (0, 1)]
    if hypot(subject_border[0] - opposite_border[0],
             subject_border[1] - opposite_border[1]) > join_tolerance_m:
        raise ValueError('Mapped lanes do not share a center boundary')
    center = [(subject_border[i] + opposite_border[i]) / 2 for i in (0, 1)]
    return {'roadway_center_point_xy': center,
            'travel_tangent_xy': [tx, ty],
            'left_road_edge_xy': [opposite_xy[i] - right[i] * opposite.lane_width / 2 for i in (0, 1)],
            'right_road_edge_xy': [subject_xy[i] + right[i] * subject.lane_width / 2 for i in (0, 1)],
            'subject_road_id': subject.road_id, 'subject_lane_id': subject.lane_id,
            'opposite_lane_id': opposite.lane_id,
            'subject_lane_width_m': float(subject.lane_width),
            'opposite_lane_width_m': float(opposite.lane_width)}


def adjacent_opposing_lane(subject):
    """Find a directly joined opposite lane; reject a median or unknown gap."""
    if subject is None:
        raise ValueError('Subject mapped lane missing')
    candidate = subject.get_left_lane()
    if candidate is None:
        raise ValueError('No adjacent opposing lane on subject left')
    directed_road_section(subject, candidate)
    return candidate


def footprint_row(ego, subject, opposite, frame, time_s):
    geometry = directed_road_section(subject, opposite)
    corners = ego.bounding_box.get_world_vertices(ego.get_transform())
    if len(corners) != 8:
        raise ValueError('Native body box does not contain eight corners')
    # Bottom vertices are selected by actual z, preserving the actor's rotation.
    bottom = sorted(corners, key=lambda point: point.z)[:4]
    geometry.update({'ego_id': str(ego.id), 'frame': int(frame),
                     'time_s': float(time_s),
                     'ego_corners': [_xy(point) for point in bottom]})
    return geometry
