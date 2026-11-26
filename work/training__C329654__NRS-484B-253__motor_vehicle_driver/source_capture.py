"""Native actor readback for the exact left-turn interaction.

The local runner supplies original CARLA actors and a map survey. This module
only samples those objects; it does not infer a legal right of way or substitute
requested controls for observed motion.
"""
from __future__ import annotations

import math


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite original " + label)
    return float(value)


def _xy(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Missing original " + label)
    return (_number(value[0], label), _number(value[1], label))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _inside(point, polygon):
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Missing surveyed intersection polygon")
    vertices = [_xy(v, "intersection vertex") for v in polygon]
    signs = []
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        if abs(cross) > 1e-7:
            signs.append(cross > 0)
    if signs and len(set(signs)) != 1:
        return False
    return True


def _kinematics(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    point = (_number(pose.location.x, "actor x"), _number(pose.location.y, "actor y"))
    speed = math.sqrt(sum(_number(getattr(velocity, axis), "velocity") ** 2 for axis in ("x", "y", "z")))
    heading = _number(pose.rotation.yaw, "actor heading")
    if not isinstance(actor.id, int) or isinstance(actor.id, bool) or actor.id <= 0:
        raise ValueError("Missing original actor identity")
    return point, speed, heading


def _distance_to_conflict(point, conflict, direction):
    return _dot((conflict[0] - point[0], conflict[1] - point[1]), direction)


def sample(native_frame, frame, time_s, case_id, ego, initial, subsequent,
           survey, left_blinker_mask, source_kind="original_native", native_map=None):
    """Sample three live actors using a measured map survey and native frame.

    `survey` is a retained Native map readback. Its opposing lane direction must
    be checked against the ego approach before any source row is emitted.
    """
    if source_kind not in ("original_native", "synthetic_cpu"):
        raise ValueError("Observed source provenance differs")
    if source_kind == "original_native" and native_map is None:
        raise ValueError("Original Native map readback required")
    if type(native_frame) is not int or native_frame < 0 or type(frame) is not int or frame < 0:
        raise ValueError("Missing Native frame identity")
    t = _number(time_s, "time")
    if abs(t - frame / 20) > 0.051:
        raise ValueError("Original frame and time drift")
    conflict = _xy(survey.get("conflict_xy_m"), "conflict point")
    survey_sha = survey.get("source_sha256")
    if not isinstance(survey_sha, str) or len(survey_sha) != 64 or any(
            char not in "0123456789abcdef" for char in survey_sha):
        raise ValueError("Missing source-hashed Native map survey")
    approach = _xy(survey.get("ego_approach_direction_xy"), "ego approach")
    opposite = _xy(survey.get("opposing_approach_direction_xy"), "opposing approach")
    route_start = _xy(survey.get("turn_start_xy_m"), "turn start")
    route_end = _xy(survey.get("turn_end_xy_m"), "turn end")
    if any(abs(math.hypot(*direction) - 1) > 0.05 for direction in (approach, opposite)):
        raise ValueError("Original approach directions are not unit vectors")
    if _dot(approach, opposite) > -0.8:
        raise ValueError("Opposing lane is not opposite to subject approach")
    if not all(isinstance(actor.id, int) for actor in (ego, initial, subsequent)) or len(
            {ego.id, initial.id, subsequent.id}) != 3:
        raise ValueError("Three distinct original actor identities required")
    start_to_end = (route_end[0] - route_start[0], route_end[1] - route_start[1])
    route_length_sq = _dot(start_to_end, start_to_end)
    if route_length_sq < 4:
        raise ValueError("Surveyed left turn route is too short")
    ego_point, ego_speed, ego_heading = _kinematics(ego)
    progress = max(0.0, min(1.0, _dot((ego_point[0] - route_start[0],
                                      ego_point[1] - route_start[1]), start_to_end) / route_length_sq))
    if not isinstance(left_blinker_mask, int) or left_blinker_mask <= 0:
        raise ValueError("Original left blinker mask missing")
    lamp = int(ego.get_light_state()) & left_blinker_mask != 0
    opponents = []
    for actor in (initial, subsequent):
        point, speed, heading = _kinematics(actor)
        lane = None
        if native_map is not None:
            lane = native_map.get_waypoint(actor.get_transform().location,
                                           project_to_road=False)
            if lane is None:
                raise ValueError("Original opposing actor lane readback absent")
            lane_heading = math.radians(_number(lane.transform.rotation.yaw, "lane heading"))
            if _dot((math.cos(lane_heading), math.sin(lane_heading)), opposite) < 0.8:
                raise ValueError("Original opposing lane direction differs")
        opponents.append({"actor_id": str(actor.id), "speed_mps": speed,
                          "distance_to_conflict_m": _distance_to_conflict(point, conflict, opposite),
                          "center_xy_m": list(point), "heading_deg": heading,
                          "approach_lane_opposite": True,
                          "native_road_id": None if lane is None else lane.road_id,
                          "native_lane_id": None if lane is None else lane.lane_id})
    return {"case_id": case_id, "source_kind": source_kind,
            "frame": frame, "native_frame": native_frame, "time_s": t,
            "ego": {"speed_mps": ego_speed, "left_turn_progress": progress,
                    "distance_to_conflict_m": _distance_to_conflict(ego_point, conflict, approach),
                    "inside_intersection": _inside(ego_point, survey.get("intersection_polygon_xy_m")),
                    "left_indicator_on": lamp, "center_xy_m": list(ego_point),
                    "heading_deg": ego_heading},
            "oncoming": opponents, "survey_source_sha256": survey_sha,
            "legal_verdict": None}
