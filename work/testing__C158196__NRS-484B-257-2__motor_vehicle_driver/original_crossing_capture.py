"""Acquire one original Native sample for subsection 2 crossing measurements.

The caller owns the CARLA world, actor lifecycle, clock and camera frame map.
No CARLA module is imported here, so source acquisition can be CPU tested.
"""

import math


def _vector_length(vector):
    value = math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)
    if not math.isfinite(value):
        raise ValueError("Nonfinite Native velocity")
    return value


def _body_vertices(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("Missing complete Native body vertices")
    points = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if any(not math.isfinite(coordinate) for point in points for coordinate in point):
        raise ValueError("Nonfinite Native body vertex")
    return points


def _lane_key(native_map, actor):
    waypoint = native_map.get_waypoint(actor.get_location())
    if waypoint is None:
        raise ValueError("Actor is outside a Native lane")
    return f"{waypoint.road_id}:{waypoint.lane_id}"


def _distance_to_conflict(actor, point):
    position = actor.get_location()
    distance = math.hypot(position.x - point.x, position.y - point.y)
    if not math.isfinite(distance):
        raise ValueError("Nonfinite conflict distance")
    return distance


def sample(world, ego, other, light, conflict_point, frame, time_s,
           ego_entrance_lane, other_entrance_lane):
    """Read same-frame actor state after the caller has ticked and joined cameras."""
    if type(frame) is not int or frame < 0 or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
        raise ValueError("Invalid original frame identity")
    native_map = world.get_map()
    current_ego_lane = _lane_key(native_map, ego)
    current_other_lane = _lane_key(native_map, other)
    if (not isinstance(ego_entrance_lane, str) or not ego_entrance_lane or
            not isinstance(other_entrance_lane, str) or not other_entrance_lane):
        raise ValueError("Missing sourced entrance lane")
    if ego_entrance_lane == other_entrance_lane:
        raise ValueError("Other vehicle must enter from a distinct lane")
    affected = {f"{wp.road_id}:{wp.lane_id}" for wp in light.get_affected_lane_waypoints()}
    if not affected:
        raise ValueError("Signal affected-lane map is empty")
    native_state = light.get_state()
    state = getattr(native_state, "name", str(native_state).split(".")[-1])
    if state not in {"Red", "Yellow", "Green", "Off"}:
        raise ValueError("Unsupported Native signal state")
    return {"frame": frame, "time_s": float(time_s), "ego_lane_key": ego_entrance_lane,
            "other_lane_key": other_entrance_lane,
            "ego_current_lane_key": current_ego_lane, "other_current_lane_key": current_other_lane,
            "ego_body_vertices_xy_m": _body_vertices(ego),
            "other_body_vertices_xy_m": _body_vertices(other),
            "signal_controls_ego": ego_entrance_lane in affected, "signal_state": state,
            "ego_speed_mps": _vector_length(ego.get_velocity()),
            "other_speed_mps": _vector_length(other.get_velocity()),
            "ego_distance_to_conflict_m": _distance_to_conflict(ego, conflict_point),
            "other_distance_to_conflict_m": _distance_to_conflict(other, conflict_point)}
