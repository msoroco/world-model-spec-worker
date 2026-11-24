"""Source-bound device-zone and parked vehicle-footprint diagnostic."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "restriction_sign", "curb_side"}
HASHES = ("native_map", "regulatory_device", "governed_zone", "device_conditions",
          "civil_time", "ego_body", "ego_motion", "exception_context", "camera_manifest")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_device_parking_readback":
        raise ValueError("Original Native parking source missing")
    for name in HASHES:
        value = context.get(name + "_sha256")
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source hash: " + name)
    if context.get("device_code") != "no_parking" or context.get("device_official") is not True:
        raise ValueError("Official no-parking device missing")
    if context.get("condition_in_effect") is not True or context.get("vehicle_action") != "park":
        raise ValueError("Device condition or parked action unresolved")
    for key in ("traffic_conflict_necessity", "law_compliance_exception", "police_direction_exception",
                "device_direction_exception"):
        if context.get(key) is not False:
            raise ValueError("Exception context unresolved: " + key)
    start = number(context.get("governed_start_x_m"), "zone start")
    end = number(context.get("governed_end_x_m"), "zone end")
    if start >= end:
        raise ValueError("Governed zone invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second trace")
    previous_native = None
    parked_frames = []
    zone_frames = []
    first_rest = None
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
        length = number(row.get("ego_length_m"), "ego length")
        speed = number(row.get("ego_speed_mps"), "ego speed")
        if length <= 0 or speed < 0:
            raise ValueError("Invalid vehicle body or motion")
        if speed <= 0.1 and row.get("parking_brake_applied") is True:
            parked_frames.append(i)
            if first_rest is None:
                first_rest = {"frame": i, "center_x_m": x, "rear_x_m": x - length / 2,
                              "front_x_m": x + length / 2}
            if x + length / 2 >= start and x - length / 2 <= end:
                zone_frames.append(i)
    if not parked_frames:
        raise ValueError("Parked stationary interval missing")
    return {"format": "worker-source-prohibited-parking-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "first_parked_frame": parked_frames[0],
            "parked_frame_count": len(parked_frames), "first_parked_body": first_rest,
            "parked_zone_overlap_frame_count": len(zone_frames),
            "device_prohibited_place_occupied_while_parked": bool(zone_frames),
            "legal_compliance": "unassessed",
            "limitations": ["Recorded rest plus applied parking brake is a diagnostic, not a complete legal park definition.",
                            "Zone overlap uses a longitudinal body interval and requires original sign scope and body/pixel review.",
                            "All statutory exceptions and device conditions need independent source review."]}
