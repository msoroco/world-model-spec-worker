"""Original-frame observations for the conditional right-lane duty.

No numeric threshold here decides when traffic is legally impeded or when
passing is necessary. Those are separate source-bound review questions.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C147344__NRS-484B-627-1b__motor_vehicle_driver"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT:
        raise ValueError("wrong assignment")
    if not packet.get("original_trace_id"):
        raise ValueError("original trace identity required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    for i, f in enumerate(frames):
        for key in ("time_s", "ego_speed_mps", "follower_gap_m", "follower_speed_mps"):
            v = f.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"frame {i}: finite {key} required")
        if f["follower_gap_m"] < 0:
            raise ValueError("follower gap must be nonnegative")
        if i and not 0 < f["time_s"] - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("times must be ordered with no skipped 20 Hz frame")
        if not f.get("ego_lane_id") or not f.get("rightmost_same_direction_lane_id"):
            raise ValueError("original lane identities required")
        if not f.get("follower_actor_id") or not f.get("follower_lane_id"):
            raise ValueError("original following actor and lane required")
        if not isinstance(f.get("passing_slower_vehicle_observed"), bool):
            raise ValueError("original passing observation required")
        if not isinstance(f.get("same_direction_marked_lane_count"), int) or f["same_direction_marked_lane_count"] < 2:
            raise ValueError("two or more marked same-direction lanes required")
        observations.append({
            "frame_index": i,
            "time_s": f["time_s"],
            "ego_in_extreme_right_lane": f["ego_lane_id"] == f["rightmost_same_direction_lane_id"],
            "follower_immediately_behind_in_ego_lane": f["follower_lane_id"] == f["ego_lane_id"],
            "follower_closing_speed_mps": f["follower_speed_mps"] - f["ego_speed_mps"],
            "follower_gap_m": f["follower_gap_m"],
            "passing_slower_vehicle_observed": f["passing_slower_vehicle_observed"],
        })
    return {
        "assignment_id": ASSIGNMENT,
        "original_trace_id": packet["original_trace_id"],
        "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "observations": observations,
        "review_limit": "Closing speed and gap do not alone prove impediment; observed passing does not alone prove necessity. Highway status, lane markings, immediately-behind relation and exception need source review.",
    }
