"""Independent postcapture isolation checks for the four planned comparisons.

The source-bound packets and original geometry audits establish observable
differences only. They never decide whether the statute was satisfied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometry_audit import audit as audit_geometry
from native_scene import inspect


def _loaded(attempt: Path, case_id: str, geometry_auditor):
    packet, case, _ = inspect(attempt / "site/packet.json",
                              Path(__file__).with_name("case-plan.json"), case_id)
    geometry = geometry_auditor(attempt)
    if geometry.get("case_id") != case_id or geometry.get("legal_judgment") != "unresolved":
        raise ValueError("original geometry audit identity differs")
    return packet, case, geometry


def compare(left: Path, right: Path, comparison_id: str,
            *, geometry_auditor=audit_geometry) -> dict:
    left, right = Path(left).resolve(), Path(right).resolve()
    plan = json.loads(Path(__file__).with_name("case-plan.json").read_text())
    item = next((c for c in plan["comparisons"]
                 if c.get("comparison_id") == comparison_id), None)
    if item is None or len(item["case_ids"]) != 2 or left == right:
        raise ValueError("exact comparison identity required")
    first, second = (_loaded(attempt, case_id, geometry_auditor)
                     for attempt, case_id in zip((left, right), item["case_ids"]))
    a, acase, ag = first
    b, bcase, bg = second
    if (a["sources"]["crossing_authority"]["sha256"] !=
            b["sources"]["crossing_authority"]["sha256"] or
            a["rail_crossing_map_ref"] != b["rail_crossing_map_ref"] or
            a["sign_landmark_id"] != b["sign_landmark_id"] or
            a["stop_line_x_m"] != b["stop_line_x_m"] or
            a["rail_line_x_m"] != b["rail_line_x_m"] or
            a["approach_direction"] != b["approach_direction"] or
            a["cameras"] != b["cameras"] or
            a["vehicle_blueprints"]["ego"] != b["vehicle_blueprints"]["ego"]):
        raise ValueError("fixed crossing authority, approach or capture differs")
    if comparison_id != "marked_lane_qualification" and (
            a["sources"]["opendrive"]["sha256"] !=
            b["sources"]["opendrive"]["sha256"] or
            a["marked_lanes"] != b["marked_lanes"] or
            a["highway_right_y_m"] != b["highway_right_y_m"] or
            a["highway_left_y_m"] != b["highway_left_y_m"]):
        raise ValueError("fixed reviewed highway geometry differs")
    if comparison_id == "two_marked_queue_arrangement":
        if (acase["traffic_arrangement"] != "one_queue" or
                bcase["traffic_arrangement"] != "two_queues" or
                acase["subject_lateral_plan"] != bcase["subject_lateral_plan"] or
                a["ego_slot"] != b["ego_slot"] or
                ag["two_queue_aligned_frame_count"] != 0 or
                bg["two_queue_aligned_frame_count"] < 20):
            raise ValueError("original queue arrangement contrast absent")
    elif comparison_id == "marked_lane_qualification":
        if (len(a["marked_lanes"]) != 2 or len(b["marked_lanes"]) < 4 or
                acase["traffic_arrangement"] != bcase["traffic_arrangement"] or
                a["ego_slot"] != b["ego_slot"] or
                min(ag["two_queue_aligned_frame_count"],
                    bg["two_queue_aligned_frame_count"]) < 20):
            raise ValueError("original marked-lane qualification contrast absent")
    else:
        if (acase["traffic_arrangement"] != bcase["traffic_arrangement"] or
                acase["subject_lateral_plan"] != "rightmost_feasible" or
                bcase["subject_lateral_plan"] != "left_of_feasible" or
                a["rightmost_feasible_slot"] != b["rightmost_feasible_slot"] or
                ag["minimum_stopped_lateral_offset_from_reviewed_rightmost_m"] is None or
                bg["minimum_stopped_lateral_offset_from_reviewed_rightmost_m"] is None or
                bg["minimum_stopped_lateral_offset_from_reviewed_rightmost_m"] -
                ag["minimum_stopped_lateral_offset_from_reviewed_rightmost_m"] < .5):
            raise ValueError("original right-side lateral contrast absent")
        if acase["traffic_arrangement"] == "two_queues" and min(
                ag["two_queue_aligned_frame_count"],
                bg["two_queue_aligned_frame_count"]) < 20:
            raise ValueError("fixed two-queue arrangement absent")
    return {"format": "c202480-independent-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": item["case_ids"],
            "fixed_conditions_checked": item["fixed_conditions"],
            "deliberate_differences_checked": item["deliberate_differences"],
            "original_geometry_audits": [ag, bg],
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    parser.add_argument("--comparison-id", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.left, args.right, args.comparison_id), indent=2))
