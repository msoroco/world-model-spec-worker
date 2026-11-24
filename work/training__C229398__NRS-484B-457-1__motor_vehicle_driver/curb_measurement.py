"""Source-bound geometry diagnostic for NRS 484B.457(1) at C229398.

This module measures a Native readback. It does not infer ordinance authority or
legal compliance from a requested parking position.
"""

import math

FRAME_COUNT = 600
RATE_HZ = 20
CAMERAS = frozenset({"overview", "ego_front", "curb_side", "wheel_closeup"})
SOURCE_HASHES = ("native_map", "right_curb_geometry", "wheel_geometry",
                 "ego_motion", "parking_state", "camera_manifest")


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Invalid " + label)
    return float(value)


def point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Invalid " + label)
    return finite(value[0], label + " x"), finite(value[1], label + " y")


def distance_to_polyline(p, vertices):
    """Return shortest metric distance and tangent of a nondegenerate curb segment."""
    best = None
    for a, b in zip(vertices, vertices[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        if length2 <= 1e-12:
            raise ValueError("Degenerate curb segment")
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
        q = a[0] + t * dx, a[1] + t * dy
        distance = math.hypot(p[0] - q[0], p[1] - q[1])
        candidate = distance, (dx / math.sqrt(length2), dy / math.sqrt(length2))
        if best is None or distance < best[0]:
            best = candidate
    return best


def measure(context, rows):
    if context.get("source_kind") != "native_c229398_wheel_curb_readback":
        raise ValueError("Native wheel/curb readback missing")
    for label in SOURCE_HASHES:
        digest = context.get(label + "_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Missing source hash: " + label)
    if context.get("highway_adjacent_curbs") is not True or context.get("right_curb_confirmed") is not True:
        raise ValueError("Right-hand adjacent curb unconfirmed")
    # This measured branch deliberately excludes permissions. The real authority
    # finding must be supplied independently before applying a legal rule.
    if context.get("ordinance_authority_status") != "unverified_no_exception_claim":
        raise ValueError("Ordinance authority cannot be inferred from scene")
    raw_curb = context.get("right_curb_polyline_xy_m")
    if not isinstance(raw_curb, list) or len(raw_curb) != 2:
        raise ValueError("Straight right curb endpoints missing")
    curb = [point(v, "curb vertex") for v in raw_curb]
    uncertainty = finite(context.get("wheel_curb_uncertainty_m"), "geometry uncertainty")
    if uncertainty < 0:
        raise ValueError("Negative geometry uncertainty")
    if not isinstance(rows, list) or len(rows) != FRAME_COUNT:
        raise ValueError("Incomplete 30-second trace")
    gaps, headings, parked_frames = [], [], []
    previous_native = None
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native_frame = row.get("native_frame")
        if type(native_frame) is not int or (previous_native is not None and native_frame <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native_frame
        if abs(finite(row.get("time_s"), "time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != i for name in CAMERAS):
            raise ValueError("Four source camera join failed")
        speed = finite(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("Negative ego speed")
        # The rest threshold identifies a diagnostic window; it is not a legal
        # definition of standing or parking.
        if speed > 0.1 or row.get("parking_brake_applied") is not True:
            continue
        center = point(row.get("ego_center_xy_m"), "ego center")
        front = point(row.get("right_front_wheel_outer_xy_m"), "right front wheel")
        rear = point(row.get("right_rear_wheel_outer_xy_m"), "right rear wheel")
        front_gap, tangent = distance_to_polyline(front, curb)
        rear_gap, _ = distance_to_polyline(rear, curb)
        # A curb on the vehicle's right is to the right of the forward heading;
        # for the authored +x road that means the curb is below the vehicle.
        heading = math.radians(finite(row.get("ego_heading_deg"), "ego heading"))
        forward = math.cos(heading), math.sin(heading)
        for wheel in (front, rear):
            lateral = forward[0] * (wheel[1] - center[1]) - forward[1] * (wheel[0] - center[0])
            if lateral >= 0:
                raise ValueError("Right wheel side inconsistent with heading")
        for wheel in (front, rear):
            lateral_to_curb = tangent[0] * (wheel[1] - curb[0][1]) - tangent[1] * (wheel[0] - curb[0][0])
            if lateral_to_curb <= 0:
                raise ValueError("Right wheel beyond curb")
        curb_heading = math.degrees(math.atan2(tangent[1], tangent[0]))
        delta = abs(((math.degrees(heading) - curb_heading + 90) % 180) - 90)
        gaps.extend((front_gap, rear_gap))
        headings.append(delta)
        parked_frames.append(i)
    if not parked_frames:
        raise ValueError("Stopped/parked diagnostic interval missing")
    low = min(gaps) - uncertainty
    high = max(gaps) + uncertainty
    boundary = 18 * 0.0254
    if high < boundary:
        bracket = "strictly_within_18_in_diagnostic"
    elif low > boundary:
        bracket = "strictly_beyond_18_in_diagnostic"
    else:
        bracket = "straddles_18_in_boundary"
    return {"format": "worker-c229398-curb-diagnostic", "frame_count": FRAME_COUNT,
            "parked_frame_count": len(parked_frames), "first_parked_frame": parked_frames[0],
            "last_parked_frame": parked_frames[-1],
            "wheel_gap_in_range": [min(gaps) / 0.0254, max(gaps) / 0.0254],
            "uncertainty_in": uncertainty / 0.0254,
            "maximum_parallel_heading_delta_deg": max(headings),
            "boundary_bracket": bracket, "legal_compliance": "unassessed",
            "source_kind": context["source_kind"]}
