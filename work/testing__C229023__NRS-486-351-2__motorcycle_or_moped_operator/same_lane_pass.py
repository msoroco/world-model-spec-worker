"""Original-frame same-lane abreast and overtaking observations.

Consent for two abreast and subsection 3 are independent source questions;
neither can be inferred from a completed maneuver.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229023__NRS-486-351-2__motorcycle_or_moped_operator"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("ego_vehicle_type") not in ("motorcycle", "moped", "trimobile"):
        raise ValueError("qualifying ego vehicle type required")
    if not packet.get("ego_actor_id") or not packet.get("other_actor_id"):
        raise ValueError("original actor identities required")
    if packet.get("subsection_3_exception_status") not in ("applies", "does_not_apply", "unresolved"):
        raise ValueError("subsection 3 exception status required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    same_lane = []
    for i, f in enumerate(frames):
        t = f.get("time_s")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("finite original time required")
        if i and not 0 < t - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        if not f.get("ego_lane_id") or not f.get("other_lane_id"):
            raise ValueError("original lane identities required")
        if f.get("longitudinal_relation") not in ("behind", "abreast", "ahead"):
            raise ValueError("original longitudinal relation required")
        if not isinstance(f.get("driver_consent_observed"), bool):
            raise ValueError("original driver consent observation required")
        if not isinstance(f.get("same_lane_two_wheeler_count"), int) or f["same_lane_two_wheeler_count"] < 0:
            raise ValueError("same-lane two-wheeler count required")
        if f["ego_lane_id"] == f["other_lane_id"]:
            same_lane.append({"frame_index": i, "relation": f["longitudinal_relation"],
                              "consent_observed": f["driver_consent_observed"],
                              "two_wheeler_count": f["same_lane_two_wheeler_count"]})
    first_behind = next((o["frame_index"] for o in same_lane if o["relation"] == "behind"), None)
    same_lane_pass = first_behind is not None and any(o["relation"] == "ahead" and o["frame_index"] > first_behind for o in same_lane)
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "ego_actor_id": packet["ego_actor_id"], "other_actor_id": packet["other_actor_id"],
            "ego_vehicle_type": packet["ego_vehicle_type"],
            "subsection_3_exception_status": packet["subsection_3_exception_status"],
            "same_lane_observations": same_lane,
            "same_lane_abreast_observed": any(o["relation"] == "abreast" for o in same_lane),
            "same_lane_pass_observed": same_lane_pass,
            "review_limit": "Two-abreast consent and subsection 3 must be reviewed from original evidence; a same-lane pass is a separate branch from consented side-by-side operation."}
