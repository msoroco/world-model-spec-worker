"""Source-bound circulatory lane occupancy and left-exit trajectory diagnostic."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "entry_lane", "exit_lane"}
HASHES = ("native_map", "roundabout_lanes", "entry_exit_links", "ego_body",
          "ego_motion", "exit_intention", "camera_manifest")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_roundabout_readback":
        raise ValueError("Original Native roundabout source missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("roundabout_topology_verified") is not True or context.get("left_exit_intention_sourced") is not True:
        raise ValueError("Roundabout topology or exit intention unsourced")
    inner = number(context.get("left_lane_center_radius_m"), "left lane radius")
    outer = number(context.get("right_lane_center_radius_m"), "right lane radius")
    half_width = number(context.get("lane_half_width_m"), "lane half width")
    if inner <= 0 or outer - inner <= 2 * half_width or half_width <= 0:
        raise ValueError("Distinct circulatory lanes missing")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    phases = []
    ring_lanes = []
    ring_angles = []
    exit_heading = None
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
        phase = row.get("phase")
        if phase not in {"entry", "circulation", "exit"}:
            raise ValueError("Unknown roadway phase")
        phases.append(phase)
        x = number(row.get("ego_x_m"), "ego x")
        y = number(row.get("ego_y_m"), "ego y")
        heading = number(row.get("ego_heading_deg"), "ego heading")
        if phase == "circulation":
            radius = math.hypot(x, y)
            lane = "left" if abs(radius - inner) <= half_width else ("right" if abs(radius - outer) <= half_width else "outside")
            ring_lanes.append(lane)
            ring_angles.append(number(row.get("unwrapped_angle_rad"), "unwrapped angle"))
        if phase == "exit":
            exit_heading = heading
    if not ring_lanes or "entry" not in phases or "exit" not in phases:
        raise ValueError("Complete roundabout entry/circulation/exit missing")
    if phases != sorted(phases, key={"entry": 0, "circulation": 1, "exit": 2}.get):
        raise ValueError("Roundabout phase ordering invalid")
    sweep = ring_angles[-1] - ring_angles[0]
    if not 4.5 <= sweep <= 4.9 or exit_heading is None or abs(((exit_heading - 180 + 180) % 360) - 180) > 10:
        raise ValueError("Left-turn exit trajectory not observed")
    if "outside" in ring_lanes:
        raise ValueError("Ego left both inventoried lanes")
    return {"format": "worker-source-roundabout-lane-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "circulation_frame_count": len(ring_lanes),
            "left_lane_frame_count": ring_lanes.count("left"),
            "right_lane_frame_count": ring_lanes.count("right"),
            "lane_change_count": sum(a != b for a, b in zip(ring_lanes, ring_lanes[1:])),
            "angular_sweep_rad": sweep, "exit_heading_deg": exit_heading,
            "legal_compliance": "unassessed",
            "limitations": ["Lane labels depend on original roundabout lane topology and body-footprint review.",
                            "Left-turn exit intention requires independent source; geometry alone cannot prove intent.",
                            "No statutory numerical lane-occupancy threshold is inferred."]}
