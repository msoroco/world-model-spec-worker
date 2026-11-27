"""Measure an original Native approach to a moving, flashing emergency vehicle."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")


def measure(context, rows):
    if context.get("source_kind") not in {"original_native_emergency_readback", "synthetic_cpu_emergency_readback"}:
        raise ValueError("Original Native or explicitly synthetic emergency readback missing")
    for name in ("native_map_sha256", "ego_blueprint_sha256", "emergency_actor_sha256",
                 "emergency_role_source_sha256", "flashing_lamp_source_sha256", "vehicle_extent_sha256",
                 "visibility_source_sha256", "officer_direction_source_sha256"):
        source_hash(context.get(name), name)
    if context.get("emergency_role") not in {"authorized_emergency", "official_regulatory"}:
        raise ValueError("Qualifying vehicle role missing")
    if context.get("lamps_meet_nrs_484a_480_3") is not True:
        raise ValueError("Qualifying flashing-lamp evidence missing")
    mode = context.get("activation_mode")
    if mode not in {"moving_vehicle", "visible_hand_signal"}:
        raise ValueError("Moving or visibly preparing activation not sourced")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    prior_native = None
    passing = []
    approaching = []
    officer = set()
    speeds = []
    gaps = []
    hard = []
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (prior_native is not None and native <= prior_native):
            raise ValueError("Native frame identity gap")
        prior_native = native
        if abs(number(row.get("time_s"), "Native time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[c] != i for c in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        if row.get("emergency_visible") not in (True, False):
            raise ValueError("Visibility observation missing")
        if row.get("flashing_lamps_visible") not in (True, False):
            raise ValueError("Flashing lamps observation missing")
        if row.get("officer_direction") not in {"none", "proceed", "stop", "other"}:
            raise ValueError("Officer direction source missing")
        if row.get("hand_signal_visible") not in (True, False):
            raise ValueError("Visible preparation source missing")
        officer.add(row["officer_direction"])
        ego_x = number(row.get("ego_center_x_m"), "ego position")
        emergency_x = number(row.get("emergency_center_x_m"), "emergency position")
        ego_speed = number(row.get("ego_speed_mps"), "ego speed")
        emergency_speed = number(row.get("emergency_speed_mps"), "emergency speed")
        gap = number(row.get("surface_gap_m"), "surface gap")
        deceleration = number(row.get("ego_deceleration_mps2"), "ego deceleration")
        if ego_speed < 0 or emergency_speed < 0 or gap < 0:
            raise ValueError("Negative speed or surface gap")
        activated = emergency_speed > 0.1 if mode == "moving_vehicle" else row["hand_signal_visible"]
        if row["emergency_visible"] and row["flashing_lamps_visible"] and activated and ego_x < emergency_x:
            approaching.append(i)
        if abs(ego_x - emergency_x) <= 4.5 and row["emergency_visible"]:
            passing.append(i)
        speeds.append(ego_speed)
        gaps.append(gap)
        hard.append(deceleration >= 3.0)
    if not approaching:
        raise ValueError("No sourced approach to moving flashing vehicle")
    if not passing:
        raise ValueError("No sourced passing interval")
    first = approaching[0]
    if not rows[first]["emergency_visible"] or not rows[first]["flashing_lamps_visible"]:
        raise ValueError("Emergency indication not visible on approach")
    first_pass = passing[0]
    relative_speed = max(0.0, speeds[first] - number(rows[first]["emergency_speed_mps"], "emergency speed"))
    longitudinal_gap = number(rows[first]["emergency_center_x_m"], "emergency x") - number(rows[first]["ego_center_x_m"], "ego x")
    ttc = longitudinal_gap / relative_speed if relative_speed > 0.01 else None
    return {"format": "worker-source-emergency-approach-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "diagnostic_only": context["source_kind"] == "synthetic_cpu_emergency_readback",
            "activation_mode": mode,
            "qualifying_role": context["emergency_role"],
            "first_approach_frame": first, "first_passing_frame": first_pass,
            "approach_time_to_conflict_s": ttc,
            "minimum_passing_surface_gap_m": min(gaps[i] for i in passing),
            "ego_speed_at_first_pass_mps": speeds[first_pass],
            "hard_deceleration_frames": [i for i, value in enumerate(hard) if value],
            "officer_direction_states": sorted(officer),
            "legal_compliance": "unassessed",
            "limitations": ["Proceed with caution is qualitative; speed, clearance, TTC and braking are diagnostics, not a statutory cutoff.",
                            "Lamp qualification, vehicle authorization, and visibility need original source and independent review.",
                            "An officer direction changes the applicable response and requires separate branch review."]}
