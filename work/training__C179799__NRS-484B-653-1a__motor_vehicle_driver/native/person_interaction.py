"""Source-shaped person interaction measurements for NRS 484B.653(1)(a).

Telemetry cannot establish a willful or wanton mental state. Controller
settings below are diagnostic trajectory choices, not legal thresholds.
"""

from __future__ import annotations

from math import hypot, isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
RESPONSE_DISTANCE_M = {"earlier_response": 30.0, "later_response": 15.0}


def control_request(mode: str, person_forward_gap_m: float) -> dict:
    if mode not in RESPONSE_DISTANCE_M:
        raise ValueError("unknown interaction control mode")
    if not isfinite(person_forward_gap_m):
        raise ValueError("invalid measured person gap")
    if person_forward_gap_m <= RESPONSE_DISTANCE_M[mode]:
        return {"throttle": 0.0, "brake": 0.7}
    return {"throttle": 0.35, "brake": 0.0}


def measure_trace(rows: list[dict], scene: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    if scene.get("access_kind") not in ("highway", "public_access_premises") or not scene.get("public_access_source"):
        raise ValueError("highway or public-access premises source required")
    if not scene.get("driver_source") or not scene.get("person_actor_source"):
        raise ValueError("driver and distinct person provenance required")
    min_gap = float("inf")
    min_ttc = float("inf")
    max_ego_speed = 0.0
    max_longitudinal_accel = 0.0
    max_abs_yaw_rate = 0.0
    contacts = 0
    min_person_accel = float("inf")
    last_person_speed = None
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        keys = ("ego_x_m", "ego_y_m", "ego_vx_mps", "ego_vy_mps", "ego_radius_m",
                "person_x_m", "person_y_m", "person_vx_mps", "person_vy_mps", "person_radius_m",
                "ego_accel_longitudinal_mps2", "ego_yaw_rate_radps")
        try:
            v = [float(row[k]) for k in keys]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("raw actor pose, velocity and control motion required") from exc
        if not all(isfinite(x) for x in v) or min(v[4], v[9]) <= 0:
            raise ValueError("invalid raw actor pose or motion")
        if type(row.get("collision_sensor_contact")) is not bool:
            raise ValueError("collision sensor source required")
        ex, ey, evx, evy, er, px, py, pvx, pvy, pr, accel, yaw = v
        dx, dy = px - ex, py - ey
        centre_gap = hypot(dx, dy)
        surface_gap = centre_gap - er - pr
        min_gap = min(min_gap, surface_gap)
        if centre_gap > 0:
            closing = -((dx * (pvx - evx) + dy * (pvy - evy)) / centre_gap)
            if surface_gap > 0 and closing > 0:
                min_ttc = min(min_ttc, surface_gap / closing)
        max_ego_speed = max(max_ego_speed, hypot(evx, evy))
        max_longitudinal_accel = max(max_longitudinal_accel, abs(accel))
        max_abs_yaw_rate = max(max_abs_yaw_rate, abs(yaw))
        person_speed = hypot(pvx, pvy)
        if last_person_speed is not None:
            min_person_accel = min(min_person_accel, (person_speed - last_person_speed) * FRAME_RATE)
        last_person_speed = person_speed
        contacts += int(row["collision_sensor_contact"])
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "minimum_person_surface_gap_m": min_gap,
        "minimum_projected_ttc_s": None if min_ttc == float("inf") else min_ttc,
        "maximum_ego_speed_mps": max_ego_speed,
        "maximum_abs_ego_longitudinal_accel_mps2": max_longitudinal_accel,
        "maximum_abs_ego_yaw_rate_radps": max_abs_yaw_rate,
        "minimum_person_accel_mps2": min_person_accel,
        "contact_frames": contacts,
        "mental_state_conclusion": None,
        "legal_recklessness_conclusion": None,
        "source_kind": "unverified_raw_actor_and_scene_fields",
    }
