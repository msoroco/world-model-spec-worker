"""Retain original Native body, velocity and frame joins for median precedence.

The caller joins all four source-camera frames to this world tick before writing.
PipelineCapture separately owns the original trace and evidence streams.
"""
import json
import math


def _finite(value, label):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite Native " + label)
    return result


def _actor_row(actor, waypoint, approach_road_id, intersection_id):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError("Missing complete Native body vertices")
    body = [[_finite(vertex.x, "body x"), _finite(vertex.y, "body y")]
            for vertex in vertices]
    velocity = actor.get_velocity()
    return {
        "actor_id": actor.id,
        "intersection_id": intersection_id,
        "road_id": approach_road_id,
        "native_road_id": waypoint.road_id,
        "native_lane_id": waypoint.lane_id,
        "native_junction_id": waypoint.get_junction().id if waypoint.is_junction else None,
        "heading_deg": _finite(transform.rotation.yaw, "heading"),
        "body_vertices_xy_m": body,
        "velocity_mps": [_finite(velocity.x, "velocity x"),
                          _finite(velocity.y, "velocity y"),
                          _finite(velocity.z, "velocity z")],
        "body_source": "actor.bounding_box.get_world_vertices",
        "velocity_source": "actor.get_velocity",
    }


def record_crossing_sample(frame_map, history_stream, snapshot, world_map,
                           ego, other, plan):
    """Append one source row and the matching original-video frame identity."""
    if plan.get("candidate_same_native_junction") is not True:
        raise ValueError("Checked Native crossing candidate required")
    frame = snapshot.frame
    time = _finite(snapshot.timestamp.elapsed_seconds, "snapshot time")
    rows = {}
    for role, actor in (("ego", ego), ("other", other)):
        waypoint = world_map.get_waypoint(actor.get_location(), project_to_road=False)
        if waypoint is None:
            raise ValueError("Participant left Native road: " + role)
        approach_road = plan["approaches"][role]["road_id"]
        rows[role] = _actor_row(actor, waypoint, approach_road,
                                plan["native_junction_id"])
    if rows["ego"]["actor_id"] == rows["other"]["actor_id"]:
        raise ValueError("Distinct Native participants required")
    mapping = frame_map.append(frame, time)
    row = {"frame": frame, "time_s": time,
           "ego_vertices_m": rows["ego"]["body_vertices_xy_m"], **rows}
    history_stream.write(json.dumps(row, allow_nan=False) + "\n")
    return {"video_frame": mapping["video_frame"], "history": row}
