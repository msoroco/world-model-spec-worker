"""Source-bound construction drafts for the six exact standing/parking cases.

No site, activity, legal result, or physical realization is inferred here.
"""
from __future__ import annotations

import math

from parking_measurement import inside, unit
from parking_pose import REQUESTS, body, construct
from source_review import validate


ASSIGNMENT = "testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver"


def build(packet_path, source_root, suffix, *, approach_distance_m=8.0,
          length_m=4.5, width_m=2.0):
    if suffix not in REQUESTS:
        raise ValueError("unknown exact standing/parking case")
    context = validate(packet_path, source_root=source_root)
    activity = REQUESTS[suffix][0]
    if context["activity"] != activity:
        raise ValueError("source-reviewed activity differs from requested case")
    pose = construct(context, suffix, length_m=length_m, width_m=width_m)
    if not math.isfinite(approach_distance_m) or approach_distance_m <= 0:
        raise ValueError("approach distance must be positive")
    target = pose["target_center_xy_m"]
    forward = (unit(context["lawful_travel_xy"])
               if pose["orientation_request"] == "angled"
               else unit(pose["target_forward_xy"]))
    spawn = [target[i] - approach_distance_m * forward[i] for i in (0, 1)]
    spawn_body = body(spawn, forward, length_m=length_m, width_m=width_m)
    if not all(inside(point, context["roadway_polygon_xy_m"]) for point in spawn_body):
        raise ValueError("approach spawn body leaves reviewed roadway")
    return {
        "case_id": ASSIGNMENT + "__" + suffix,
        "source_packet_sha256": context["reviewed_packet_sha256"],
        "source_hashes": {name: context[name] for name in
                          ("roadway_source", "road_edge_source", "lawful_direction_source",
                           "activity_source", "chapter_exception_source")},
        "activity_request": activity,
        "chapter_exception_review": context["chapter_exception_review"],
        "spawn_center_xy_m": spawn,
        "spawn_forward_xy": list(forward),
        "spawn_body_vertices_xy_m": spawn_body,
        "waypoint_centers_xy_m": [spawn, list(target)],
        "target_pose": pose,
        "controller_kind": "approach_then_stationary_hold",
        "physical_risk": {
            "risk": "A finite footprint may fail to reach or hold the requested pose on a one-way roadway",
            "trigger": "Original pose or speed history departs from engineering target during the hold",
            "fallback_status": "not_constructed"
        },
        "original_observations_required": ["body_vertices_xy_m", "vehicle_forward_xy",
                                           "speed_m_s", "control", "frame", "time_s"],
        "physical_realization_claimed": False,
        "legal_judgment": "unresolved",
    }
