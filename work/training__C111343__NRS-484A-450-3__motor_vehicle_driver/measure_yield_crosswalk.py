"""Source-bound conditional yield stop position against a near-side crosswalk."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
HASHES = ("native_map", "yield_sign", "near_crosswalk", "ego_body", "ego_motion",
          "intersecting_traffic", "safety_context", "camera_manifest")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    source_kind = context.get("source_kind")
    if source_kind not in {"original_native_yield_crosswalk_readback", "synthetic_yield_fixture"}:
        raise ValueError("Yield source kind missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("governing_yield_sign") is not True or context.get("near_side_crosswalk") is not True:
        raise ValueError("Governing yield sign and near-side crosswalk required")
    if context.get("safety_context_present") is not True or context.get("safety_stop_required") != "unassessed":
        raise ValueError("Conditional safety context missing or legal judgment invented")
    near = number(context.get("crosswalk_near_x_m"), "crosswalk near edge")
    far = number(context.get("crosswalk_far_x_m"), "crosswalk far edge")
    intersection = number(context.get("intersection_near_x_m"), "intersection near edge")
    if not near < far < intersection:
        raise ValueError("Crosswalk and intersection ordering invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    previous_front = None
    stopped = []
    first_crosswalk = None
    first_intersection = None
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
        if (not isinstance(cameras, dict) or set(cameras) != CAMERAS
                or any(cameras[name] != native for name in CAMERAS)):
            raise ValueError("Four source camera join failed")
        x = number(row.get("ego_x_m"), "ego x")
        length = number(row.get("ego_length_m"), "ego length")
        speed = number(row.get("ego_speed_mps"), "ego speed")
        other = number(row.get("intersecting_vehicle_y_m"), "intersecting vehicle y")
        if length <= 0 or speed < 0:
            raise ValueError("Invalid vehicle body or motion")
        front = x + length / 2
        if previous_front is not None and front < previous_front - 0.001:
            raise ValueError("Ego reversed on approach")
        previous_front = front
        if first_crosswalk is None and front >= near:
            first_crosswalk = i
        if first_intersection is None and front >= intersection:
            first_intersection = i
        if speed <= 0.1:
            stopped.append({"frame": i, "front_x_m": front, "before_near_edge": front < near,
                            "in_crosswalk": near <= front <= far, "intersecting_vehicle_y_m": other})
    if not stopped or first_crosswalk is None or first_intersection is None:
        raise ValueError("Stop and complete approach missing")
    first_stop = stopped[0]
    return {"format": "worker-source-yield-crosswalk-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "first_stop_frame": first_stop["frame"],
            "first_stop_front_x_m": first_stop["front_x_m"],
            "first_stop_before_crosswalk": first_stop["before_near_edge"],
            "first_stop_in_crosswalk": first_stop["in_crosswalk"],
            "stopped_frame_count": len(stopped), "first_crosswalk_entry_frame": first_crosswalk,
            "first_intersection_entry_frame": first_intersection,
            "intersecting_vehicle_y_at_stop_m": first_stop["intersecting_vehicle_y_m"],
            "safety_stop_requirement": "unassessed", "legal_compliance": "unassessed",
            "limitations": ["0.1 m/s is a recorded-rest diagnostic, not a statutory threshold.",
                            "Whether safety requires a stop remains a sourced independent judgment.",
                            "Original crosswalk, sign, traffic and body pixels require later review."]}
