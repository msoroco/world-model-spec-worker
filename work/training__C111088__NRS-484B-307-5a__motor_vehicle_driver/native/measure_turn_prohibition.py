"""Source-bound sole-straight-arrow turn observation for a separate maneuver branch."""

import math

FRAMES = 840
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
    if context.get("source_kind") != "original_native_straight_arrow_turn_readback":
        raise ValueError("Original straight-arrow source missing")
    for name in ("native_map_sha256", "intersection_geometry_sha256", "governing_signal_actor_sha256",
                 "signal_phase_source_sha256", "ego_body_source_sha256", "ego_pose_source_sha256",
                 "signal_pixel_review_sha256"):
        source_hash(context.get(name), name)
    if context.get("signal_face_verified") is not True or context.get("sole_straight_arrow_verified") is not True:
        raise ValueError("Governing sole straight arrow not sourced")
    if context.get("ego_route_direction") not in {"straight", "left", "right"}:
        raise ValueError("Ego route direction missing")
    bounds = context.get("intersection_x_bounds_m")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError("Intersection bounds missing")
    low, high = [finite(v, "intersection bound") for v in bounds]
    if low >= high or len(rows) != FRAMES:
        raise ValueError("Invalid bounds or incomplete 42-second Native trace")
    prior_native = None
    inside = []
    headings = []
    phases = []
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
        x = finite(row.get("ego_center_x_m"), "ego x")
        heading = finite(row.get("ego_heading_deg"), "ego heading")
        phase = row.get("governing_phase")
        if phase not in {"sole_green_straight_arrow", "other"}:
            raise ValueError("Governing signal phase missing")
        if row.get("additional_turn_lamp_on") not in (True, False):
            raise ValueError("Additional turn lamp observation missing")
        if low <= x <= high:
            inside.append(i)
        headings.append(heading)
        phases.append(phase == "sole_green_straight_arrow" and row["additional_turn_lamp_on"] is False)
    if not inside:
        raise ValueError("No observed intersection entry")
    if not all(phases[i] for i in inside):
        raise ValueError("Sole straight arrow not maintained during intersection occupancy")
    initial = headings[inside[0]]
    heading_change = max(abs(((headings[i] - initial + 180) % 360) - 180) for i in inside)
    turn_observed = heading_change >= 30
    return {"format": "worker-source-straight-arrow-turn-observation",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "first_intersection_frame": inside[0], "last_intersection_frame": inside[-1],
            "maximum_heading_change_in_intersection_deg": heading_change,
            "turn_observed_by_30_degree_diagnostic": turn_observed,
            "requested_route_direction": context["ego_route_direction"],
            "legal_compliance": "unassessed",
            "limitations": ["Thirty degrees is a motion diagnostic, not the statutory definition of a turn.",
                            "The governing signal face and lamp exclusivity require original actor and pixel review.",
                            "A turn-attempt branch needs a compatible frozen cell or approved source-bound extension."]}
