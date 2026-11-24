"""Case-specific, measured backing response witnesses.

Thresholds below distinguish the two engineered controller policies. They do
not define statutory yielding or establish pedestrian right of way.
"""
from __future__ import annotations

from math import isfinite


WINDOW_FRAMES = 20
MIN_FRAME = 20


def response_witness(measurement, *, case_id):
    if case_id.endswith("__pedestrian_yield"):
        policy = "pedestrian_yield"
    elif case_id.endswith("__pedestrian_continue"):
        policy = "pedestrian_continue"
    else:
        raise ValueError("unknown backing response case")
    frames = measurement.get("frames")
    if not isinstance(frames, list) or len(frames) < WINDOW_FRAMES:
        raise ValueError("original measured response frames missing")
    for start in range(len(frames) - WINDOW_FRAMES + 1):
        window = frames[start:start + WINDOW_FRAMES]
        if window[0]["frame"] < MIN_FRAME:
            continue
        if any(row["frame"] != window[0]["frame"] + offset
               for offset, row in enumerate(window)):
            continue
        if not all(row["pedestrian_in_corridor"] and row["pedestrian_speed_mps"] > .05
                   and row["reverse_gear"] for row in window):
            continue
        if not all(isfinite(row["brake"]) and isfinite(row["reverse_speed_mps"])
                   for row in window):
            raise ValueError("nonfinite original driver response")
        if policy == "pedestrian_yield":
            matched = all(row["brake"] >= .5 and row["reverse_speed_mps"] <= .3
                          for row in window)
        else:
            matched = all(row["brake"] <= .1 and row["reverse_speed_mps"] >= .4
                          for row in window)
        if matched:
            return {"policy": policy, "source_id": measurement["source_id"],
                    "first_frame": window[0]["frame"], "last_frame": window[-1]["frame"],
                    "pedestrian_speed_min_mps": min(row["pedestrian_speed_mps"] for row in window),
                    "reverse_speed_min_mps": min(row["reverse_speed_mps"] for row in window),
                    "reverse_speed_max_mps": max(row["reverse_speed_mps"] for row in window),
                    "brake_min": min(row["brake"] for row in window),
                    "brake_max": max(row["brake"] for row in window),
                    "witness_kind": "original_frame_engineering_response",
                    "legal_judgment": "unresolved"}
    raise ValueError("case-specific moving-pedestrian response witness missing")
