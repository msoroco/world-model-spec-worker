"""Original-frame road-envelope measurements for passing on the right.

The operative word 'requires' is kept distinct from merely observing an
off-pavement path. Geometric fit is a lower bound, not a safety judgment.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C182383__NRS-484B-210-3__motor_vehicle_driver"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    result = measure_data(packet)
    result["source"] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return result


def measure_data(packet: dict) -> dict:
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if not packet.get("ego_actor_id") or not packet.get("overtaken_actor_id"):
        raise ValueError("original vehicle identities required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    for i, f in enumerate(frames):
        for key in ("time_s", "ego_left_m", "ego_right_m", "overtaken_left_m", "overtaken_right_m", "paved_left_m", "paved_right_m"):
            v = f.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"frame {i}: original finite {key} required")
        if i and not 0 < f["time_s"] - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        if not (f["paved_left_m"] < f["paved_right_m"] and f["ego_left_m"] < f["ego_right_m"] and f["overtaken_left_m"] < f["overtaken_right_m"]):
            raise ValueError("invalid original lateral envelopes")
        for key in ("longitudinal_overlap", "ego_ahead_of_overtaken"):
            if not isinstance(f.get(key), bool):
                raise ValueError(f"original {key} readback required")
        if f["longitudinal_overlap"]:
            width = f["ego_right_m"] - f["ego_left_m"]
            corridor = f["paved_right_m"] - f["overtaken_right_m"]
            observations.append({"frame_index": i,
                                 "ego_to_right_of_overtaken": f["ego_left_m"] >= f["overtaken_right_m"],
                                 "ego_body_off_pavement_m": max(0.0, f["ego_right_m"] - f["paved_right_m"]),
                                 "right_side_paved_corridor_m": corridor,
                                 "ego_body_width_m": width,
                                 "no_zero_clearance_fit_on_pavement": corridor < width})
    expected_pass = packet.get("expected_pass", True)
    if not isinstance(expected_pass, bool):
        raise ValueError("expected pass status must be source-typed")
    if not expected_pass:
        if frames[0]["ego_ahead_of_overtaken"] or frames[-1]["ego_ahead_of_overtaken"]:
            raise ValueError("no-pass control has completed overtaking")
        observations = []
    else:
        if not observations or not frames[-1]["ego_ahead_of_overtaken"] or frames[0]["ego_ahead_of_overtaken"]:
            raise ValueError("complete right-side pass event required")
        if not any(o["ego_to_right_of_overtaken"] for o in observations):
            raise ValueError("right-side overlap not observed")
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "right_pass_completed": expected_pass,
            "ego_actor_id": packet["ego_actor_id"], "overtaken_actor_id": packet["overtaken_actor_id"],
            "overlap_observations": observations,
            "actual_off_pavement_observed": any(o["ego_body_off_pavement_m"] > 0 for o in observations),
            "zero_clearance_paved_fit_impossible_observed": any(o["no_zero_clearance_fit_on_pavement"] for o in observations),
            "review_limit": "A zero-clearance body fit cannot establish a safe lawful alternative. Actual off-pavement motion alone does not establish that the movement required leaving the paved portion."}
