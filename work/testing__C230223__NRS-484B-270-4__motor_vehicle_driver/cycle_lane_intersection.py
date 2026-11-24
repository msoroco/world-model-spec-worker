"""Original-frame motor-vehicle occupation of a cycle lane at an intersection.

Lane designation, intersection boundary and subsection 3 exception are
separate source facts; painted marks alone do not prove designation.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C230223__NRS-484B-270-4__motor_vehicle_driver"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("ego_vehicle_type") != "motor_vehicle" or not packet.get("ego_actor_id"):
        raise ValueError("original motor-vehicle identity required")
    if not packet.get("intersection_id") or not packet.get("cycle_lane_id"):
        raise ValueError("original intersection and cycle-lane identities required")
    if packet.get("cycle_lane_designated_for") not in ("bicycle", "electric_bicycle", "electric_scooter", "mixed_cycle"):
        raise ValueError("source cycle-lane designation required")
    if packet.get("subsection_3_exception_status") not in ("applies", "does_not_apply", "unresolved"):
        raise ValueError("subsection 3 exception status required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    for i, f in enumerate(frames):
        t = f.get("time_s")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("finite original time required")
        if i and not 0 < t - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        for key in ("ego_body_in_intersection", "ego_body_in_designated_cycle_lane"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} readback required")
        observations.append({"frame_index": i, "time_s": t,
                             "in_intersection": f["ego_body_in_intersection"],
                             "in_designated_cycle_lane": f["ego_body_in_designated_cycle_lane"],
                             "intersection_and_cycle_lane_overlap": f["ego_body_in_intersection"] and f["ego_body_in_designated_cycle_lane"]})
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "ego_actor_id": packet["ego_actor_id"], "intersection_id": packet["intersection_id"],
            "cycle_lane_id": packet["cycle_lane_id"], "cycle_lane_designated_for": packet["cycle_lane_designated_for"],
            "subsection_3_exception_status": packet["subsection_3_exception_status"],
            "observations": observations,
            "vehicle_in_cycle_lane_within_intersection_observed": any(o["intersection_and_cycle_lane_overlap"] for o in observations),
            "review_limit": "The subsection 3 exception remains an independent question; verify original intersection polygon and cycle-path designation before legal use."}
