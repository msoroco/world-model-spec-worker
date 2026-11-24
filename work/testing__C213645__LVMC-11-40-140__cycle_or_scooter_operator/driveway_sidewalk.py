"""Source-bound stop and pedestrian observations at a driveway sidewalk.

The distance to the last stop is reported, not judged against an invented
numeric meaning of 'immediately prior'. Collision avoidance needs review.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C213645__LVMC-11-40-140__cycle_or_scooter_operator"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("vehicle_type") not in ("bicycle", "electric_bicycle", "electric_scooter"):
        raise ValueError("qualifying cycle or scooter type required")
    if packet.get("district_type") not in ("business", "residence") or not packet.get("district_source_id"):
        raise ValueError("source-bound business or residence district required")
    if packet.get("access_type") not in ("driveway", "alley", "building") or not packet.get("sidewalk_area_id"):
        raise ValueError("original access and sidewalk-area identity required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    for i, f in enumerate(frames):
        for key in ("time_s", "speed_mps", "distance_before_sidewalk_edge_m"):
            v = f.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"original finite {key} required")
        if f["speed_mps"] < 0:
            raise ValueError("negative speed")
        if i and not 0 < f["time_s"] - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        for key in ("pedestrian_in_conflict_area", "operator_yield_observed"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} readback required")
        if not isinstance(f.get("pedestrian_actor_ids"), list):
            raise ValueError("pedestrian actor identity list required")
    entry = next((i for i in range(1, len(frames)) if frames[i]["distance_before_sidewalk_edge_m"] <= 0 < frames[i - 1]["distance_before_sidewalk_edge_m"]), None)
    if entry is None:
        raise ValueError("original sidewalk entry bracket required")
    stopped = [i for i in range(entry) if frames[i]["speed_mps"] <= 0.1]
    last_stop = stopped[-1] if stopped else None
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "vehicle_type": packet["vehicle_type"], "district_type": packet["district_type"],
            "district_source_id": packet["district_source_id"], "access_type": packet["access_type"],
            "sidewalk_area_id": packet["sidewalk_area_id"], "entry_bracket_indices": [entry - 1, entry],
            "last_pre_entry_stop_index": last_stop,
            "last_stop_distance_before_edge_m": frames[last_stop]["distance_before_sidewalk_edge_m"] if last_stop is not None else None,
            "pedestrian_conflict_observed_at_entry": frames[entry]["pedestrian_in_conflict_area"],
            "pedestrian_actor_ids_at_entry": frames[entry]["pedestrian_actor_ids"],
            "operator_yield_observed_at_entry": frames[entry]["operator_yield_observed"],
            "review_limit": "A sampled low speed and pedestrian presence do not alone establish a legal stop, immediate proximity, collision necessity or sufficient yielding; inspect original motion and geometry."}
