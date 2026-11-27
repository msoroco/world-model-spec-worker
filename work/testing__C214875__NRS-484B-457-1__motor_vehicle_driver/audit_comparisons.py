"""Independent source-bound right-curb controlled comparison checks."""
from __future__ import annotations

import json
from pathlib import Path

from audit_original_attempt import audit
from curb_geometry import ASSIGNMENT

PAIRS = {
    "inside_vs_boundary": ("park_17in_parallel", "park_18in_parallel"),
    "boundary_vs_outside": ("park_18in_parallel", "park_19in_parallel"),
    "parallel_vs_skew": ("park_17in_parallel", "park_17in_skew"),
    "park_vs_stop": ("park_18in_parallel", "stop_18in_parallel"),
}


def compare(comparison_id, first_attempt, second_attempt):
    pair = PAIRS.get(comparison_id)
    if pair is None:
        raise ValueError("unknown exact right-curb comparison")
    attempts = (Path(first_attempt), Path(second_attempt))
    case_ids = [ASSIGNMENT + "__" + name for name in pair]
    audited = [audit(path, case_id) for path, case_id in zip(attempts, case_ids)]
    original = [path / "original-attempt" for path in attempts]
    sites = [json.loads((path / "site.json").read_text()) for path in original]
    plans = [json.loads((path / "plan.json").read_text()) for path in original]
    inventories = [json.loads((path / "inventory.json").read_text()) for path in original]
    if sites[0]["sources"] != sites[1]["sources"] or \
            sites[0]["reviewed_assertions"] != sites[1]["reviewed_assertions"] or \
            sites[0]["right_curb_xy_m"] != sites[1]["right_curb_xy_m"] or \
            sites[0]["parking_route_xy_m"] != sites[1]["parking_route_xy_m"]:
        raise ValueError("fixed reviewed curb site or exception source differs")
    if plans[0]["candidate_id"] != plans[1]["candidate_id"] or \
            plans[0]["capture"] != plans[1]["capture"] or \
            plans[0]["reviewed_sources"] != plans[1]["reviewed_sources"] or \
            inventories[0]["rate_hz"] != inventories[1]["rate_hz"] or \
            inventories[0]["frame_count"] != inventories[1]["frame_count"]:
        raise ValueError("fixed original capture context differs")
    a, b = (item["measurement"] for item in audited)
    da = a["max_right_wheel_distance_inches"]
    db = b["max_right_wheel_distance_inches"]
    aa = a["max_wheel_curb_alignment_deg"]
    ab = b["max_wheel_curb_alignment_deg"]
    if comparison_id in ("inside_vs_boundary", "boundary_vs_outside"):
        if not db > da or abs(ab - aa) > .2 or not a["parking_brake_frames"] or not b["parking_brake_frames"]:
            raise ValueError("original curb boundary contrast absent")
    elif comparison_id == "parallel_vs_skew":
        if not ab > aa + 2 or abs(db - da) > .1 or not a["parking_brake_frames"] or not b["parking_brake_frames"]:
            raise ValueError("original curb alignment contrast absent")
    else:
        if abs(db - da) > .1 or abs(ab - aa) > .2 or \
                not a["parking_brake_frames"] or not b["stopped_without_parking_brake_frames"]:
            raise ValueError("original parked versus stopped contrast absent")
    return {"comparison_id": comparison_id, "case_ids": case_ids,
            "fixed_source_and_capture_checked": True,
            "observed_distances_inches": [da, db],
            "observed_alignment_deg": [aa, ab],
            "original_activity_checked": True,
            "physical_acceptance": False, "legal_judgment": "unresolved"}
