"""Retain Native actor geometry and four camera identities at each tick.

These are original simulator readbacks, not camera-visible direction or a
legal control judgment. A later reviewer must bind independent observations.
"""

import math

from officer_camera import CAMERAS


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite Native " + label + " required")
    return float(value)


def _body(actor, label):
    if type(getattr(actor, "id", None)) is not int:
        raise ValueError("Native " + label + " identity required")
    box = getattr(actor, "bounding_box", None)
    if box is None or not hasattr(box, "get_world_vertices"):
        raise ValueError("Native " + label + " bounding box required")
    vertices = box.get_world_vertices(actor.get_transform())
    if not isinstance(vertices, (tuple, list)) or len(vertices) < 4:
        raise ValueError("Complete Native " + label + " body required")
    points = [[_finite(vertex.x, label + " x"), _finite(vertex.y, label + " y")]
              for vertex in vertices]
    velocity = actor.get_velocity()
    speed = math.sqrt(sum(_finite(getattr(velocity, axis), label + " velocity") ** 2
                          for axis in ("x", "y", "z")))
    return {"actor_id": actor.id, "body_vertices_xy_m": points,
            "speed_mps": speed}


def record(world, ego, other, frame_row):
    if not isinstance(frame_row, dict) or type(frame_row.get("carla_frame")) is not int:
        raise ValueError("Native frame receipt required")
    snapshot = world.get_snapshot()
    frame = getattr(snapshot, "frame", None)
    time_s = _finite(getattr(getattr(snapshot, "timestamp", None),
                             "elapsed_seconds", None), "snapshot time")
    if frame != frame_row["carla_frame"]:
        raise ValueError("Native snapshot differs from camera frame")
    cameras = frame_row.get("camera_raw_sources")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("Four original camera frame sources required")
    for name in CAMERAS:
        if cameras[name].get("carla_frame") != frame or not cameras[name].get("raw_source"):
            raise ValueError("Original camera frame source differs: " + name)
    officer = frame_row.get("officer_program")
    if (not isinstance(officer, dict) or
            officer.get("frame_index") != frame_row.get("frame_index")):
        raise ValueError("Programmed officer pose differs from Native frame")
    return {"frame": frame, "time_s": time_s,
            "ego": _body(ego, "ego"), "other": _body(other, "other"),
            "officer_actor_id": officer.get("officer_actor_id"),
            "programmed_direction": officer.get("programmed_direction"),
            "native_pose_applied": officer.get("pose_applied"),
            "camera_frames": {name: cameras[name]["carla_frame"] for name in CAMERAS},
            "camera_raw_sources": {name: cameras[name]["raw_source"] for name in CAMERAS},
            "officer_direction_observed": "unreviewed",
            "actual_police_control_observed": "unreviewed"}
