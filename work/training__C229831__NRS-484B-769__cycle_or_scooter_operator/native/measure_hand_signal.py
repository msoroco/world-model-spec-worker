"""Diagnostic rider-arm geometry from retained raw keypoint and route sources.

The numerical tolerances are engineering checks, not NRS 484B.420 definitions.
The result never asserts a legal signal or physical completion.
"""
from __future__ import annotations

from math import acos, hypot, isfinite, sin, cos

FPS = 20
FRAMES = 600


def _xy(row, name):
    value = row.get(name)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"missing raw keypoint {name}")
    x, y = map(float, value)
    if not isfinite(x) or not isfinite(y):
        raise ValueError(f"nonfinite raw keypoint {name}")
    return x, y


def measure(rows: list[dict], context: dict) -> dict:
    """Join 600 timestamped body/keypoint samples to a sourced roadway turn."""
    if len(rows) != FRAMES:
        raise ValueError("30-second 20-Hz source trace required")
    required = ("machine_class_source", "operator_id_source", "roadway_polygon_source",
                "connected_right_turn_route_source", "keypoint_capture_source",
                "camera_calibration_source")
    if any(not context.get(k) for k in required):
        raise ValueError("sourced machine, operator, roadway, route and keypoints required")
    if context.get("machine_class") not in {"bicycle", "electric_bicycle", "electric_scooter"}:
        raise ValueError("covered machine class required")
    if context.get("derived_channels_used"):
        raise ValueError("derived hand-signal channel cannot replace raw keypoints")
    extension = []
    roadway_frames = 0
    turn_frames = 0
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(float(row.get("time_s", -1)) - i / FPS) > 1e-8:
            raise ValueError("frame identity or 20-Hz join failed")
        if row.get("operator_id") != context.get("operator_id"):
            raise ValueError("operator identity join failed")
        if type(row.get("roadway_occupied")) is not bool or type(row.get("on_right_turn_route")) is not bool:
            raise ValueError("raw roadway occupancy and turn route samples required")
        roadway_frames += row["roadway_occupied"]
        turn_frames += row["on_right_turn_route"]
        shoulder = _xy(row, "right_shoulder_xy_m")
        elbow = _xy(row, "right_elbow_xy_m")
        wrist = _xy(row, "right_wrist_xy_m")
        centre = _xy(row, "machine_centre_xy_m")
        heading = float(row.get("machine_heading_rad", float("nan")))
        if not isfinite(heading):
            raise ValueError("raw machine heading required")
        # In right-handed road coordinates, machine right points clockwise.
        rx, ry = sin(heading), -cos(heading)
        arm_x, arm_y = wrist[0] - shoulder[0], wrist[1] - shoulder[1]
        length = hypot(arm_x, arm_y)
        elbow_length = hypot(elbow[0] - shoulder[0], elbow[1] - shoulder[1])
        if not 0.15 <= length <= 1.2 or not 0.05 <= elbow_length <= 0.9:
            raise ValueError("unphysical or absent arm keypoints")
        rightward = arm_x * rx + arm_y * ry
        machine_right = (wrist[0] - centre[0]) * rx + (wrist[1] - centre[1]) * ry
        elbow_right = (elbow[0] - shoulder[0]) * rx + (elbow[1] - shoulder[1]) * ry
        forearm_x, forearm_y = wrist[0] - elbow[0], wrist[1] - elbow[1]
        forearm_length = hypot(forearm_x, forearm_y)
        if forearm_length < 0.05:
            raise ValueError("unphysical or absent arm keypoints")
        cosine = ((elbow[0] - shoulder[0]) * forearm_x +
                  (elbow[1] - shoulder[1]) * forearm_y) / (elbow_length * forearm_length)
        straight = acos(max(-1.0, min(1.0, cosine)))
        extended = (rightward >= 0.35 and machine_right >= 0.35 and
                    elbow_right >= 0.12 and straight <= 0.45)
        if extended and row["roadway_occupied"] and row["on_right_turn_route"]:
            extension.append(i)
    if not roadway_frames or not turn_frames:
        raise ValueError("roadway occupancy and connected right turn required")
    runs = []
    for frame in extension:
        if not runs or frame != runs[-1][-1] + 1:
            runs.append([frame])
        else:
            runs[-1].append(frame)
    return {
        "frames": FRAMES, "duration_s": FRAMES / FPS,
        "machine_class": context["machine_class"],
        "roadway_occupied_frames": roadway_frames,
        "right_turn_route_frames": turn_frames,
        "right_arm_horizontal_rightward_runs": [
            {"first_frame": run[0], "last_frame": run[-1], "duration_s": len(run) / FPS}
            for run in runs
        ],
        "right_arm_extension_observed": bool(extension),
        "signal_meaning": None,
        "general_NRS_484B_420_method_conclusion": None,
        "NRS_484B_769_conclusion": None,
        "source_kind": "unverified_raw_keypoints_and_route",
    }
