"""Source-bound divided-highway left-turn and median crossing meter."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference", "driver"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Missing source hash: " + name)


def measure(context, rows):
    if context.get("source_kind") != "original_native_divided_highway_readback":
        raise ValueError("Original divided-highway source missing")
    for name in ("native_map_sha256", "divider_geometry_sha256", "roadway_direction_sha256",
                 "physical_opening_sha256", "vehicle_extent_sha256", "ego_pose_source_sha256"):
        source_hash(context.get(name), name)
    authority = context.get("public_authority_crossover_established")
    if authority not in (True, False, None):
        raise ValueError("Invalid public-authority disposition")
    if authority is True:
        source_hash(context.get("public_authority_crossover_sha256"),
                    "public_authority_crossover_sha256")
    low, high = [finite(x, "authorized opening bound") for x in context.get("opening_x_m", [])]
    median_low, median_high = [finite(x, "median y bound") for x in context.get("median_y_m", [])]
    if low >= high or median_low >= median_high:
        raise ValueError("Invalid opening or median geometry")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    median_frames = []
    crossing_x = []
    crossing_footprints = []
    left_turn_frames = []
    semicircular_turn_frames = []
    u_turn_frames = []
    wrong_roadway_frames = []
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != i for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        x = finite(row.get("ego_center_x_m"), "ego x")
        y = finite(row.get("ego_center_y_m"), "ego y")
        width = finite(row.get("ego_width_m"), "ego width")
        length = finite(row.get("ego_length_m"), "ego length")
        if width <= 0 or length <= 0:
            raise ValueError("Invalid ego extent")
        if row.get("left_turn_active") not in (True, False):
            raise ValueError("Left turn state missing")
        if row.get("semicircular_turn_active") not in (True, False):
            raise ValueError("Semicircular turn state missing")
        if row.get("u_turn_active") not in (True, False):
            raise ValueError("U-turn state missing")
        if row.get("roadway_direction") not in {"right_hand", "opposite", "median"}:
            raise ValueError("Roadway direction source missing")
        intersects_median = y + width / 2 >= median_low and y - width / 2 <= median_high
        if intersects_median:
            median_frames.append(i)
            crossing_x.append(x)
            crossing_footprints.append((x-length/2, x+length/2))
        if row["left_turn_active"]:
            left_turn_frames.append(i)
        if row["semicircular_turn_active"]:
            semicircular_turn_frames.append(i)
        if row["u_turn_active"]:
            u_turn_frames.append(i)
        if row["roadway_direction"] == "opposite":
            wrong_roadway_frames.append(i)
    if not median_frames:
        raise ValueError("No observed median footprint overlap")
    turns = left_turn_frames+semicircular_turn_frames+u_turn_frames
    if not turns:
        raise ValueError("No observed turn")
    if max(turns) < min(median_frames) or min(turns) > max(median_frames):
        raise ValueError("Turn does not coincide with median crossing")
    in_opening = [low <= x <= high for x in crossing_x]
    footprint_in_opening = [low <= left and right <= high for left,right in crossing_footprints]
    return {"format": "worker-source-divided-highway-median-crossing-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "first_median_footprint_frame": median_frames[0],
            "last_median_footprint_frame": median_frames[-1],
            "median_crossing_center_x_range_m": [min(crossing_x), max(crossing_x)],
            "all_median_overlap_centers_within_authorized_opening": all(in_opening),
            "median_overlap_frames_outside_authorized_opening": sum(not value for value in in_opening),
            "all_median_overlap_footprints_within_physical_opening": all(footprint_in_opening),
            "median_overlap_frames_with_footprint_outside_opening": sum(not value for value in footprint_in_opening),
            "public_authority_crossover_established": authority,
            "wrong_roadway_frame_count": len(wrong_roadway_frames),
            "observed_left_turn": bool(left_turn_frames),
            "observed_semicircular_turn": bool(semicircular_turn_frames),
            "observed_u_turn": bool(u_turn_frames),
            "legal_compliance": "unassessed",
            "limitations": ["Sourced footprint extent and position do not establish physical traversability or video visibility.",
                            "A physical opening and a public-authority crossover are separate statutory permissions.",
                            "Original road geometry, source authority, continuous roadway duty and turn classification need independent review."]}
