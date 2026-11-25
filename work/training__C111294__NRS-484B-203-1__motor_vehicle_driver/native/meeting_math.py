"""Source-bound opposite-direction meeting and paved-half footprint measurement."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Missing source hash: " + name)


def measure(context, rows):
    if context.get("source_kind") != "original_native_opposite_meeting_readback":
        raise ValueError("Original opposite-meeting source missing")
    for name in ("native_map_sha256", "paved_bounds_sha256", "lane_direction_sha256",
                 "ego_body_sha256", "oncoming_body_sha256", "vehicle_motion_sha256"):
        source_hash(context.get(name), name)
    if context.get("one_lane_each_direction_verified") is not True:
        raise ValueError("One lane per direction not sourced")
    left = finite(context.get("paved_left_y_m"), "paved left bound")
    right = finite(context.get("paved_right_y_m"), "paved right bound")
    center = finite(context.get("paved_center_y_m"), "paved centre")
    if not left < center < right or abs(center - (left + right) / 2) > 0.01:
        raise ValueError("Paved centre or bounds invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    prior_native = None
    meetings = []
    right_fraction = []
    lateral_gaps = []
    pass_right = []
    paved_width_available_to_oncoming = []
    paved_width_available_to_ego = []
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (prior_native is not None and native <= prior_native):
            raise ValueError("Native frame identity gap")
        prior_native = native
        if abs(finite(row.get("time_s"), "Native time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != i for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        ego_x = finite(row.get("ego_x_m"), "ego x")
        other_x = finite(row.get("oncoming_x_m"), "oncoming x")
        ego_y = finite(row.get("ego_y_m"), "ego y")
        other_y = finite(row.get("oncoming_y_m"), "oncoming y")
        ego_width = finite(row.get("ego_width_m"), "ego width")
        other_width = finite(row.get("oncoming_width_m"), "oncoming width")
        ego_vx = finite(row.get("ego_vx_mps"), "ego east velocity")
        other_vx = finite(row.get("oncoming_vx_mps"), "oncoming east velocity")
        if ego_width <= 0 or other_width <= 0 or ego_vx <= 0 or other_vx >= 0:
            raise ValueError("Opposite motion or vehicle extent missing")
        if abs(ego_x - other_x) <= 5:
            meetings.append(i)
            ego_low, ego_high = ego_y - ego_width / 2, ego_y + ego_width / 2
            other_low = other_y - other_width / 2
            overlap = max(0.0, min(ego_high, center) - max(ego_low, left))
            right_fraction.append(overlap / ego_width)
            lateral_gaps.append(other_low - ego_high)
            pass_right.append(ego_y < other_y)
            paved_width_available_to_oncoming.append(max(0.0, right - max(left, ego_high)))
            paved_width_available_to_ego.append(max(0.0, min(right, other_low) - left))
    if not meetings:
        raise ValueError("No observed opposite-direction meeting")
    return {"format": "worker-source-opposite-meeting-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "first_meeting_frame": meetings[0], "last_meeting_frame": meetings[-1],
            "ego_right_paved_half_footprint_fraction_min": min(right_fraction),
            "ego_right_paved_half_footprint_fraction_max": max(right_fraction),
            "minimum_lateral_surface_gap_m": min(lateral_gaps),
            "ego_passed_to_right_of_other_center": all(pass_right),
            "paved_width_m": right - left,
            "right_passing_condition": {"observed": all(pass_right), "source": "both vehicle centers and signed longitudinal velocities at every meeting frame"},
            "one_half_paved_portion_condition": {
                "minimum_width_available_to_oncoming_m": min(paved_width_available_to_oncoming),
                "minimum_fraction_available_to_oncoming": min(paved_width_available_to_oncoming) / (right - left),
                "minimum_width_available_to_ego_m": min(paved_width_available_to_ego),
                "minimum_fraction_available_to_ego": min(paved_width_available_to_ego) / (right - left),
                "source": "both vehicle body footprints and surveyed paved edges at every meeting frame",
                "as_nearly_as_possible": "unassessed"},
            "legal_compliance": "unassessed",
            "limitations": ["Vehicle-footprint fraction is an engineering diagnostic, not the statutory allocation of at least half the paved portion.",
                            "Available paved width is a geometric proxy; final statutory allocation needs original pixel and constraint review.",
                            "As nearly as possible requires original road and surrounding constraints review.",
                            "Both opposite-direction bodies, pavement edges and lane count require original source and pixel review."]}
