"""Source-shaped oncoming beam controller and measurements for NRS 484D.215(1).

Lamp API state and distance do not establish emitted light aim, glare at an
oncoming driver's eyes, or sufficient forward illumination.
"""

from __future__ import annotations

from math import hypot, isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
FIVE_HUNDRED_FEET_M = 152.4


def requested_beam(oncoming_distance_m: float | None) -> str:
    if oncoming_distance_m is None:
        return "high_beam"
    if not isfinite(oncoming_distance_m) or oncoming_distance_m < 0:
        raise ValueError("invalid measured oncoming distance")
    return "low_beam" if oncoming_distance_m <= FIVE_HUNDRED_FEET_M else "high_beam"


def measure_trace(rows: list[dict], scene: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    if scene.get("road_position") not in ("traveled_portion", "adjacent_shoulder") or not scene.get("road_source"):
        raise ValueError("traveled roadway or adjacent shoulder source required")
    if scene.get("lighting_trigger") not in ("night_interval", "poor_visibility", "official_device") or not scene.get("trigger_source"):
        raise ValueError("NRS 484D.100 lighting-trigger source required")
    if not scene.get("oncoming_driver_source") or not scene.get("eye_region_source"):
        raise ValueError("oncoming driver and eye-region sources required")
    within_frames = 0
    low_within_frames = 0
    high_within_frames = 0
    minimum_distance = float("inf")
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        keys = ("ego_x_m", "ego_y_m", "ego_heading_x", "ego_heading_y",
                "oncoming_x_m", "oncoming_y_m", "oncoming_heading_x", "oncoming_heading_y")
        try:
            v = [float(row[k]) for k in keys]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("raw actor position and heading required") from exc
        if not all(isfinite(x) for x in v):
            raise ValueError("invalid raw actor position and heading")
        ex, ey, ehx, ehy, ox, oy, ohx, ohy = v
        en, on = hypot(ehx, ehy), hypot(ohx, ohy)
        if en <= 0 or on <= 0 or (ehx*ohx + ehy*ohy)/(en*on) > -0.5:
            raise ValueError("oncoming opposed headings required")
        state = row.get("requested_beam_state")
        if state not in ("high_beam", "low_beam") or not row.get("lamp_state_source"):
            raise ValueError("source-bound headlamp request required")
        if type(row.get("eye_region_pixels_retained")) is not bool:
            raise ValueError("oncoming eye-region pixel source required")
        distance = hypot(ox-ex, oy-ey)
        minimum_distance = min(minimum_distance, distance)
        if distance <= FIVE_HUNDRED_FEET_M:
            within_frames += 1
            low_within_frames += int(state == "low_beam")
            high_within_frames += int(state == "high_beam")
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "minimum_centre_distance_m": minimum_distance,
        "within_500_feet_frames": within_frames,
        "low_beam_request_within_500_feet_frames": low_within_frames,
        "high_beam_request_within_500_feet_frames": high_within_frames,
        "glare_at_eyes_conclusion": None,
        "sufficient_forward_illumination_conclusion": None,
        "source_kind": "unverified_raw_actor_lamp_and_pixel_fields",
    }
