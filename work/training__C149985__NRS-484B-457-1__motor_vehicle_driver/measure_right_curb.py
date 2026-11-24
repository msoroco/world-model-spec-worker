"""Source-bound right-wheel clearance and parallel parking diagnostic."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "curb_side", "wheel_closeup"}
HASHES = ("native_map", "right_curb", "left_curb", "wheel_geometry", "ego_body",
          "ego_motion", "parking_state", "ordinance_context", "camera_manifest")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_right_curb_readback":
        raise ValueError("Original Native curb source missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("highway_has_adjacent_curbs") is not True or context.get("right_curb_verified") is not True:
        raise ValueError("Adjacent right-hand curb unsourced")
    if context.get("left_curb_ordinance_permits") is not False or context.get("angle_parking_ordinance_permits") is not False:
        raise ValueError("Ordinance exception unresolved")
    curb_y = number(context.get("right_curb_y_m"), "right curb y")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    parked = []
    front_gaps = []
    rear_gaps = []
    heading_deltas = []
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
        speed = number(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("Invalid vehicle speed")
        if speed <= 0.1 and row.get("parking_brake_applied") is True:
            front = number(row.get("right_front_wheel_outer_y_m"), "right front wheel") - curb_y
            rear = number(row.get("right_rear_wheel_outer_y_m"), "right rear wheel") - curb_y
            if front < 0 or rear < 0:
                raise ValueError("Wheel beyond curb")
            heading = number(row.get("ego_heading_deg"), "ego heading")
            curb_heading = number(row.get("curb_heading_deg"), "curb heading")
            delta = abs(((heading - curb_heading + 180) % 360) - 180)
            parked.append(i)
            front_gaps.append(front * 39.37007874015748)
            rear_gaps.append(rear * 39.37007874015748)
            heading_deltas.append(delta)
    if not parked:
        raise ValueError("Stopped or parked interval missing")
    return {"format": "worker-source-right-curb-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "parked_frame_count": len(parked), "first_parked_frame": parked[0],
            "right_front_wheel_gap_in_min": min(front_gaps),
            "right_front_wheel_gap_in_max": max(front_gaps),
            "right_rear_wheel_gap_in_min": min(rear_gaps),
            "right_rear_wheel_gap_in_max": max(rear_gaps),
            "maximum_heading_difference_deg": max(heading_deltas),
            "legal_compliance": "unassessed",
            "limitations": ["Exact 18-inch boundary requires original wheel and curb geometry with uncertainty review.",
                            "Parking brake and 0.1 m/s rest are engineering diagnostics, not legal definitions.",
                            "Ordinance applicability and DOT angle-parking exception require independent authority."]}
