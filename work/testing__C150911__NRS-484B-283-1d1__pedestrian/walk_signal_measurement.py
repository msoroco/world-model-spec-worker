"""Original-frame observations for a WALK indication and crosswalk entry.

Pedestrian permission and the separate vehicle-driver duty are reported
separately. Listed statutory exceptions require independent source review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C150911__NRS-484B-283-1d1__pedestrian"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if not packet.get("pedestrian_actor_id") or not packet.get("crosswalk_id") or not packet.get("pedestrian_signal_id"):
        raise ValueError("pedestrian, crosswalk and signal identities required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    for i, f in enumerate(frames):
        t = f.get("time_s")
        if isinstance(t, bool) or not isinstance(t, (int, float)):
            raise ValueError("original time required")
        if i and not 0 < t - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz samples required")
        if f.get("signal_indication") not in ("walk", "dont_walk", "wait", "dark"):
            raise ValueError("original pedestrian signal indication required")
        for key in ("pedestrian_facing_signal", "pedestrian_in_crosswalk", "crossing_direction_matches_signal", "driver_yield_observed"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} observation required")
        if not isinstance(f.get("driver_actor_ids"), list):
            raise ValueError("driver actor identity list required")
    entry = next((i for i in range(1, len(frames)) if frames[i]["pedestrian_in_crosswalk"] and not frames[i - 1]["pedestrian_in_crosswalk"]), None)
    if entry is None:
        raise ValueError("no observed crosswalk entry")
    f = frames[entry]
    return {
        "assignment_id": ASSIGNMENT,
        "original_trace_id": packet["original_trace_id"],
        "pedestrian_actor_id": packet["pedestrian_actor_id"],
        "crosswalk_id": packet["crosswalk_id"],
        "pedestrian_signal_id": packet["pedestrian_signal_id"],
        "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "entry_bracket_indices": [entry - 1, entry],
        "signal_at_entry": f["signal_indication"],
        "facing_at_entry": f["pedestrian_facing_signal"],
        "direction_matches_at_entry": f["crossing_direction_matches_signal"],
        "walk_permission_conditions_observed": f["signal_indication"] == "walk" and f["pedestrian_facing_signal"] and f["crossing_direction_matches_signal"],
        "driver_actor_ids_at_entry": f["driver_actor_ids"],
        "driver_yield_observed_at_entry": f["driver_yield_observed"],
        "qualification": "Driver right-of-way duty is separate from pedestrian permission. NRS 484B.287, 484B.290 and 484B.350 exceptions remain independent review questions; this observation does not decide them.",
    }
