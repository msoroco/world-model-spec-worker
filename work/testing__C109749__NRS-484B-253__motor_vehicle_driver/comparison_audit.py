"""Independent measured comparison checks for exact NRS 484B.253 pairs.

This audit checks source joins and declared variables. It never judges whether
right-of-way was legally yielded or whether an approach was an immediate hazard.
"""

import json
from pathlib import Path

from saved_left_turn import ASSIGNMENT_ID

VARIABLES = {
    "initial_within_yield": ("ego_braking", "ego_turn_committed"),
    "approaching_hazard_yield": ("ego_braking", "ego_turn_committed"),
    "opponent_location": ("opponent",),
    "signal_condition": ("ego_signal_left",),
    "reciprocal_duty": ("opponent_speed_mps", "opponent_cleared"),
}


def audit(*, plan_path, comparison_id, left, right):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan.get("assignment_id") != ASSIGNMENT_ID or comparison_id not in VARIABLES:
        raise ValueError("exact assignment comparison required")
    matches = [item for item in plan.get("comparisons", [])
               if item.get("comparison_id") == comparison_id]
    if len(matches) != 1 or len(matches[0].get("case_ids", [])) != 2:
        raise ValueError("comparison missing exact pair")
    expected = matches[0]["case_ids"]
    if [left.get("case_id"), right.get("case_id")] != expected:
        raise ValueError("comparison exact case order mismatch")
    if left.get("source_id") == right.get("source_id") or not left.get("source_id") or not right.get("source_id"):
        raise ValueError("comparison needs distinct original sources")
    if left.get("map_sha256") != right.get("map_sha256") or not left.get("map_sha256"):
        raise ValueError("comparison Native map differs")
    if left.get("physical_acceptance") != "unverified" or right.get("physical_acceptance") != "unverified":
        raise ValueError("audit input status has been rewritten")
    rows_a, rows_b = left.get("frames", []), right.get("frames", [])
    if not rows_a or len(rows_a) != len(rows_b):
        raise ValueError("comparison frame windows differ")
    if [(x["frame"], x["time_s"]) for x in rows_a] != [(x["frame"], x["time_s"]) for x in rows_b]:
        raise ValueError("comparison frame/time joins differ")
    changed = VARIABLES[comparison_id]
    if not any(a[key] != b[key] for a, b in zip(rows_a, rows_b) for key in changed):
        raise ValueError("declared measured difference absent")
    if comparison_id in ("initial_within_yield", "approaching_hazard_yield", "signal_condition"):
        for a, b in zip(rows_a, rows_b):
            for key in ("opponent", "opponent_speed_mps", "opponent_cleared", "heading_cosine"):
                if a[key] != b[key]:
                    raise ValueError("fixed opponent condition changed")
    if comparison_id == "signal_condition":
        for a, b in zip(rows_a, rows_b):
            for key in ("ego", "ego_speed_mps", "ego_braking", "ego_turn_committed"):
                if a[key] != b[key]:
                    raise ValueError("fixed ego turn condition changed")
    if comparison_id == "reciprocal_duty":
        for a, b in zip(rows_a, rows_b):
            if not a["ego_signal_left"] or not b["ego_signal_left"]:
                raise ValueError("reciprocal pair lacks observed left signal")
            for key in ("ego", "ego_speed_mps", "ego_braking", "ego_turn_committed"):
                if a[key] != b[key]:
                    raise ValueError("fixed ego turn condition changed")
    return {"assignment_id": ASSIGNMENT_ID, "comparison_id": comparison_id,
            "case_ids": expected, "source_ids": [left["source_id"], right["source_id"]],
            "checked_frames": len(rows_a), "declared_measured_difference": list(changed),
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}
