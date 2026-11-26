"""Source-bound rider position and adjacent-path condition measurement.

The output separates observed travel from the legal judgment that a path is
usable. Synthetic tests prove only the software measurement contract.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C233829__LVMC-11-40-120__cycle_or_scooter_operator"
DEVICES = {"bicycle", "electric_bicycle", "electric_scooter"}


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    return measure_packet(packet, {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})


def measure_packet(packet: dict, source: dict) -> dict:
    """Measure an already authenticated saved packet without a second copy."""
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if packet.get("ego_device_type") not in DEVICES or not packet.get("ego_actor_id"):
        raise ValueError("covered rider/device identity required")
    if not packet.get("roadway_id") or not packet.get("path_id") or not packet.get("path_designation_source"):
        raise ValueError("roadway, adjacent path and designation source required")
    if packet.get("path_adjacent_to_roadway") is not True:
        raise ValueError("source path adjacency required")
    if packet.get("sidewalk_status") not in ("absent", "present", "unresolved"):
        raise ValueError("source sidewalk status required")
    if packet.get("path_usability_status") not in ("usable", "unusable", "unresolved"):
        raise ValueError("separately reviewed path usability required")
    if not packet.get("path_condition_source") or not packet.get("access_restrictions_source"):
        raise ValueError("path condition and access restriction sources required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    previous = None
    for i, frame in enumerate(frames):
        t = frame.get("time_s")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("finite original frame time required")
        if previous is not None and not 0 < t - previous <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        previous = t
        for key in ("ego_body_on_roadway", "ego_body_on_designated_path"):
            if not isinstance(frame.get(key), bool):
                raise ValueError(f"original {key} readback required")
        observations.append({"frame_index": i, "time_s": t,
                             "on_roadway": frame["ego_body_on_roadway"],
                             "on_designated_path": frame["ego_body_on_designated_path"]})
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": source,
            "ego_actor_id": packet["ego_actor_id"], "ego_device_type": packet["ego_device_type"],
            "roadway_id": packet["roadway_id"], "path_id": packet["path_id"],
            "path_designation_source": packet["path_designation_source"],
            "path_condition_source": packet["path_condition_source"],
            "access_restrictions_source": packet["access_restrictions_source"],
            "sidewalk_status": packet["sidewalk_status"],
            "path_usability_status": packet["path_usability_status"],
            "observations": observations,
            "roadway_use_observed": any(o["on_roadway"] for o in observations),
            "path_use_observed": any(o["on_designated_path"] for o in observations),
            "review_limit": "Observed position does not decide path usability, access permission, jurisdiction or legal compliance."}
