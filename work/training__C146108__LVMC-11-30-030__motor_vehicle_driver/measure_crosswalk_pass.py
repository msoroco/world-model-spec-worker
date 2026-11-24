"""Source-bound rear approach, pedestrian crossing and stopped-vehicle pass diagnostic."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "crosswalk_side", "lead_rear"}
HASHES = ("native_map", "crosswalk_marking", "lane_directions", "ego_body", "lead_body",
          "ego_motion", "lead_motion", "pedestrian_body_motion", "camera_manifest")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_crosswalk_pass_readback":
        raise ValueError("Original Native crosswalk-pass source missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("marked_crosswalk") is not True or context.get("same_direction_rear_approach") is not True:
        raise ValueError("Marked crosswalk or rear approach unsourced")
    if context.get("lead_stopped_for_pedestrian_sourced") is not True:
        raise ValueError("Purpose of lead stop unsourced")
    crosswalk_near = number(context.get("crosswalk_near_x_m"), "crosswalk near edge")
    crosswalk_far = number(context.get("crosswalk_far_x_m"), "crosswalk far edge")
    lead_x = number(context.get("lead_center_x_m"), "lead center")
    if not lead_x < crosswalk_near < crosswalk_far:
        raise ValueError("Lead and crosswalk geometry invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    initial_behind = None
    passed_frames = []
    adjacent_overlap_frames = []
    pedestrian_crossing_frames = []
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(number(row.get("time_s"), "time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != i for name in CAMERAS):
            raise ValueError("Four source camera join failed")
        ego_x = number(row.get("ego_x_m"), "ego x")
        ego_y = number(row.get("ego_y_m"), "ego y")
        ego_length = number(row.get("ego_length_m"), "ego length")
        lead_length = number(row.get("lead_length_m"), "lead length")
        lead_speed = number(row.get("lead_speed_mps"), "lead speed")
        ped_y = number(row.get("pedestrian_y_m"), "pedestrian y")
        if ego_length <= 0 or lead_length <= 0 or lead_speed > 0.1 or lead_speed < 0:
            raise ValueError("Lead not stopped or vehicle extent invalid")
        if i == 0:
            initial_behind = ego_x + ego_length / 2 < lead_x - lead_length / 2
        crossing = -4 <= ped_y <= 4
        if crossing:
            pedestrian_crossing_frames.append(i)
        overlap = ego_x + ego_length / 2 >= lead_x - lead_length / 2 and ego_x - ego_length / 2 <= lead_x + lead_length / 2
        adjacent = abs(ego_y - number(row.get("lead_y_m"), "lead y")) >= 2.75
        if overlap and adjacent:
            adjacent_overlap_frames.append(i)
        if ego_x - ego_length / 2 > lead_x + lead_length / 2 and adjacent and crossing:
            passed_frames.append(i)
    if not initial_behind or not pedestrian_crossing_frames:
        raise ValueError("Rear approach or pedestrian crossing missing")
    return {"format": "worker-source-crosswalk-pass-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "pedestrian_crossing_frame_count": len(pedestrian_crossing_frames),
            "adjacent_longitudinal_overlap_frames": adjacent_overlap_frames,
            "passed_lead_during_pedestrian_crossing_frames": passed_frames,
            "pass_observed": bool(adjacent_overlap_frames and passed_frames),
            "legal_compliance": "unassessed",
            "limitations": ["Pass requires original body extents, lane direction and continuous trajectory review.",
                            "Purpose of stopped lead vehicle is a sourced context, not inferred from mere proximity.",
                            "Synthetic frames do not prove real pedestrian behavior or legal outcome."]}
