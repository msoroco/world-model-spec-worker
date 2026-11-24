"""Original-frame observations for crossing outside any crosswalk.

The marked/unmarked crosswalk exclusion and 11.30.070 prohibited-place
condition must come from original site evidence, not a visual guess.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C228096__LVMC-11-30-060-A__pedestrian"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    site = packet.get("site")
    if not isinstance(site, dict) or not site.get("roadway_id") or not site.get("crossing_point_id"):
        raise ValueError("original roadway and crossing-point identity required")
    for key in ("within_marked_crosswalk", "within_unmarked_intersection_crosswalk", "prohibited_place_under_11_30_070"):
        if not isinstance(site.get(key), bool):
            raise ValueError(f"original {key} site readback required")
    if site["within_marked_crosswalk"] or site["within_unmarked_intersection_crosswalk"]:
        raise ValueError("crosswalk is outside this branch")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    for i, f in enumerate(frames):
        v = f.get("time_s")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError("finite original time required")
        if i and not 0 < v - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        for key in ("pedestrian_on_roadway", "pedestrian_yield_observed"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} readback required")
        if not isinstance(f.get("vehicles_on_roadway"), list) or not all(isinstance(x, str) and x for x in f["vehicles_on_roadway"]):
            raise ValueError("original vehicle-on-roadway identity list required")
    entry = next((i for i in range(1, len(frames)) if frames[i]["pedestrian_on_roadway"] and not frames[i - 1]["pedestrian_on_roadway"]), None)
    if entry is None:
        raise ValueError("original road-entry bracket required")
    f = frames[entry]
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "roadway_id": site["roadway_id"], "crossing_point_id": site["crossing_point_id"],
            "prohibited_place_under_11_30_070": site["prohibited_place_under_11_30_070"],
            "road_entry_bracket_indices": [entry - 1, entry],
            "vehicles_on_roadway_at_entry": f["vehicles_on_roadway"],
            "pedestrian_yield_observed_at_entry": f["pedestrian_yield_observed"],
            "review_limit": "Yield at entry alone does not prove right-of-way was maintained throughout crossing. If 11.30.070 prohibits crossing, this section's stated exception needs separate review."}
