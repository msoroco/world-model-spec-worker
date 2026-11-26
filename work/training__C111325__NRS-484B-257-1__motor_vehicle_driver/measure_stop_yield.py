"""Source-bound geometric observations for the marked-line stop-sign branch."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
HASHES = ("map", "stop_sign", "stop_line", "through_road", "vehicle_bodies",
          "vehicle_motion", "control_state", "visibility")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_stop_yield_readback":
        raise ValueError("Original Native source missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("sign") != "stop" or context.get("marked_stop_line") is not True:
        raise ValueError("Governing stop sign and marked line required")
    if context.get("police_controlling") is not False or context.get("signal_controlling") is not False:
        raise ValueError("Police or signal control exception unresolved")
    line_x = number(context.get("stop_line_x_m"), "stop line")
    near_x = number(context.get("intersection_near_x_m"), "intersection near edge")
    far_x = number(context.get("intersection_far_x_m"), "intersection far edge")
    if not line_x < near_x < far_x:
        raise ValueError("Stop line and intersection ordering invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    previous_front = None
    first_line = None
    first_entry = None
    final_exit = None
    prior_stop_frames = []
    overlapping_frames = []
    through_occupancy_at_entry = None
    minimum_gap = None
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
        x = number(row.get("ego_x_m"), "ego x")
        speed = number(row.get("ego_speed_mps"), "ego speed")
        length = number(row.get("ego_length_m"), "ego length")
        other_y = number(row.get("through_vehicle_y_m"), "through vehicle y")
        other_speed = number(row.get("through_vehicle_speed_mps"), "through vehicle speed")
        if speed < 0 or length <= 0 or other_speed <= 0:
            raise ValueError("Invalid vehicle motion or body")
        front = x + length / 2
        rear = x - length / 2
        if previous_front is not None and front < previous_front - 0.001:
            raise ValueError("Ego reversed on governed approach")
        previous_front = front
        if first_line is None and front >= line_x:
            first_line = i
        if first_line is None and front < line_x and speed <= 0.1:
            prior_stop_frames.append(i)
        inside = front >= near_x and rear <= far_x
        if inside:
            if first_entry is None:
                first_entry = i
                through_occupancy_at_entry = abs(other_y) <= 4
            if abs(other_y) <= 4:
                overlapping_frames.append(i)
            gap = abs(other_y) - 4
            minimum_gap = gap if minimum_gap is None else min(minimum_gap, gap)
        elif first_entry is not None and final_exit is None:
            final_exit = i - 1
    if first_line is None or first_entry is None or final_exit is None:
        raise ValueError("Stop-line crossing and complete intersection traversal missing")
    return {"format": "worker-source-stop-yield-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "first_line_crossing_frame": first_line,
            "first_intersection_entry_frame": first_entry, "last_intersection_frame": final_exit,
            "pre_line_stopped_frame_count": len(prior_stop_frames),
            "first_pre_line_stopped_frame": prior_stop_frames[0] if prior_stop_frames else None,
            "through_road_occupied_at_entry": through_occupancy_at_entry,
            "simultaneous_intersection_occupancy_frames": overlapping_frames,
            "minimum_through_vehicle_distance_to_conflict_edge_m": minimum_gap,
            "legal_immediate_hazard": "unassessed", "legal_compliance": "unassessed",
            "limitations": ["0.1 m/s is an engineering diagnostic for recorded rest, not a statutory cutoff.",
                            "Intersection occupancy uses body extents and requires original Native body and road readback.",
                            "Immediate hazard and right-of-way remain independent judgments over original motion and pixels."]}
