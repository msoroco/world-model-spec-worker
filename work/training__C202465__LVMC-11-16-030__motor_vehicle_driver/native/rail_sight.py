"""Source-shaped crossing sight and speed measurements for LVMC 11.16.030.

This measures the 100-foot approach, 400-foot rail sight extents and traversal
speed. A diagnostic ray or control request alone cannot prove legal visibility.
"""

from __future__ import annotations

from math import isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
HUNDRED_FEET_M = 30.48
FOUR_HUNDRED_FEET_M = 121.92
FIFTEEN_MPH_MPS = 6.7056
TARGET_SPEED_MPS = {"slower_traversal": 6.0, "faster_traversal": 7.5}


def speed_request(mode: str) -> float:
    if mode not in TARGET_SPEED_MPS:
        raise ValueError("unknown traversal comparison mode")
    return TARGET_SPEED_MPS[mode]


def measure_trace(rows: list[dict], crossing: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    if not crossing.get("grade_crossing_source") or not crossing.get("railway_source") or not crossing.get("approach_route_source"):
        raise ValueError("grade crossing, railway and approach route provenance required")
    approach = []
    traversal_speeds = []
    missing_view = 0
    flagman = 0
    inactive_signal = 0
    started_outside = False
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        keys = ("distance_to_crossing_m", "speed_mps", "rail_left_clear_distance_m", "rail_right_clear_distance_m")
        try:
            distance, speed, left, right = (float(row[k]) for k in keys)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("raw approach speed and two-direction rail sight required") from exc
        if not all(isfinite(v) for v in (distance, speed, left, right)) or speed < 0 or left < 0 or right < 0:
            raise ValueError("invalid raw approach or rail sight distance")
        for key in ("traversing_grade_crossing", "crossing_visible", "left_traffic_visible", "right_traffic_visible", "flagman_on_duty", "crossing_signal_installed_visible", "signal_indicates_train_approach"):
            if type(row.get(key)) is not bool:
                raise ValueError("crossing, visibility and exception sources required")
        if not row.get("observer_pose_source") or not row.get("rail_ray_source"):
            raise ValueError("dynamic observer and two-direction ray source required")
        started_outside |= distance > HUNDRED_FEET_M
        if 0 < distance <= HUNDRED_FEET_M:
            approach.append(row)
            clear_both = (row["crossing_visible"] and left >= FOUR_HUNDRED_FEET_M and right >= FOUR_HUNDRED_FEET_M and row["left_traffic_visible"] and row["right_traffic_visible"])
            missing_view += int(not clear_both)
        if row["traversing_grade_crossing"]:
            traversal_speeds.append(speed)
        flagman += int(row["flagman_on_duty"])
        inactive_signal += int(row["crossing_signal_installed_visible"] and not row["signal_indicates_train_approach"])
    if not started_outside or not approach or not traversal_speeds:
        raise ValueError("complete approach and grade-crossing traversal required")
    if len({r["observer_pose_source"] for r in approach}) < 2:
        raise ValueError("moving observer source required throughout approach")
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "last_100_feet_sample_frames": len(approach),
        "last_100_feet_missing_view_frames": missing_view,
        "maximum_traversal_speed_mps": max(traversal_speeds),
        "fifteen_mph_mps": FIFTEEN_MPH_MPS,
        "flagman_on_duty_frames": flagman,
        "visible_inactive_signal_frames": inactive_signal,
        "legal_visibility_conclusion": None,
        "legal_exception_conclusion": None,
        "source_kind": "unverified_raw_rail_rays_and_actor_fields",
    }
