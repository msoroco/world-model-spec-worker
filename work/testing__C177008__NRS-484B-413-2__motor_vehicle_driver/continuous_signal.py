"""Original-pose path distance with continuous turn-signal history.

This measures the statutory 100/300-foot distance using original sampled
motion and signal readback. It does not infer district classification.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C177008__NRS-484B-413-2__motor_vehicle_driver"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    district = packet.get("district_type")
    if district not in ("business", "residential", "other") or not packet.get("district_source_id"):
        raise ValueError("source-bound district classification required")
    direction = packet.get("turn_direction")
    if direction not in ("left", "right"):
        raise ValueError("turn direction required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    for i, f in enumerate(frames):
        for key in ("time_s", "x_m", "y_m"):
            v = f.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"original finite {key} required")
        for key in ("left_signal", "right_signal", "course_change_begun"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} readback required")
        if i and not 0 < f["time_s"] - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
    event = next((i for i, f in enumerate(frames) if f["course_change_begun"]), None)
    if event is None or event == 0:
        raise ValueError("original course-change bracket required")
    signal_key = direction + "_signal"
    wrong_key = ("left" if direction == "right" else "right") + "_signal"
    onset = event
    while onset > 0 and frames[onset - 1][signal_key] and not frames[onset - 1][wrong_key]:
        onset -= 1
    if not (frames[event][signal_key] and not frames[event][wrong_key]):
        onset = event + 1
    distance = sum(math.hypot(frames[i]["x_m"] - frames[i - 1]["x_m"],
                              frames[i]["y_m"] - frames[i - 1]["y_m"])
                   for i in range(onset + 1, event + 1)) if onset <= event else 0.0
    required = 30.48 if district in ("business", "residential") else 91.44
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "district_type": district, "district_source_id": packet["district_source_id"],
            "turn_direction": direction, "course_change_bracket_indices": [event - 1, event],
            "continuous_signal_onset_index": onset if onset <= event else None,
            "continuous_signal_distance_m": distance,
            "statutory_distance_m": required,
            "continuous_signal_distance_sufficient": distance >= required,
            "qualification": "Original district boundary, signal API state and first course change need source review; weather does not change the statutory distance."}
