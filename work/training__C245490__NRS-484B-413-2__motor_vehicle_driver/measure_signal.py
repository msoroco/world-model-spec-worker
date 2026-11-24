"""Measure observed, continuously signaled path distance before a course change.

The caller must establish provenance of the saved sample stream and area class.
This module does not turn a commanded signal schedule into an observation.
"""
from __future__ import annotations

import math


FT_PER_M = 1 / 0.3048


def measure(rows: list[dict], area_class: str) -> dict:
    if area_class not in ("business_or_residential", "other"):
        raise ValueError("verified area class required")
    if len(rows) < 3:
        raise ValueError("at least three saved samples required")
    for index, row in enumerate(rows):
        if row.get("frame") != index:
            raise ValueError("missing or reordered saved frame")
        time = row.get("time_s")
        if type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError("invalid saved time")
        if index and abs((time - rows[index - 1]["time_s"]) - 0.05) > 1e-4:
            raise ValueError("saved 20 Hz time discontinuity")
        xy = row.get("ego_xy_m")
        if not isinstance(xy, (list, tuple)) or len(xy) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in xy
        ):
            raise ValueError("missing observed pose")
        if row.get("turn_indicator") not in ("left", "right", "off"):
            raise ValueError("missing observed indicator state")
        if type(row.get("course_change")) is not bool:
            raise ValueError("missing observed course-change event")
    events = [i for i, row in enumerate(rows) if row["course_change"]]
    if len(events) != 1 or events[0] <= 1:
        raise ValueError("one observable course-change event required")
    event = events[0]
    direction = rows[event]["turn_indicator"]
    if direction == "off":
        return {"observed_continuous_distance_ft": 0.0, "threshold_ft":
                100 if area_class == "business_or_residential" else 300,
                "onset_frame": None, "event_frame": event, "sampled_signal_continuity": False}
    onset = event
    while onset > 0 and rows[onset - 1]["turn_indicator"] == direction:
        onset -= 1
    if onset == 0:
        raise ValueError("signal onset outside saved capture")
    distance_m = 0.0
    for i in range(onset + 1, event + 1):
        a, b = rows[i - 1]["ego_xy_m"], rows[i]["ego_xy_m"]
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if not 0 < step < 10:
            raise ValueError("missing observed path movement")
        distance_m += step
    return {"observed_continuous_distance_ft": distance_m * FT_PER_M,
            "threshold_ft": 100 if area_class == "business_or_residential" else 300,
            "onset_frame": onset, "event_frame": event,
            "sampled_signal_continuity": True}
