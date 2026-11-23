"""Independent saved-source audit of near-stand right versus straight attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from candidate_opendrive import inspect as inspect_map
from delivery_audit import audit_source_chain
from stand_route import inspect as inspect_layout
from turn_trace_finalizer import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
CASES = ("near_stand", "near_stand_straight")


def compare_receipts(right: dict, straight: dict, layout_right: dict,
                     layout_straight: dict, map_hash: str) -> dict:
    inspect_layout(layout_right)
    inspect_layout(layout_straight)
    if layout_right["case"] != CASES[0] or layout_straight["case"] != CASES[1]:
        raise ValueError("turn pair selected another layout")
    for key in ("stand", "departure", "posted_notice", "road_lanes",
                "directed_edges", "intersection_order"):
        if layout_right[key] != layout_straight[key]:
            raise ValueError("turn pair changed fixed candidate geometry: " + key)
    expected_routes = ((110, 11, True), (120, 12, False))
    for case, receipt, (junction, exit_road, right_seen) in zip(
            CASES, (right, straight), expected_routes):
        measured = receipt.get("measurement", {})
        if (receipt.get("format") != "c150530-saved-source-audit-v1" or
                receipt.get("passed") is not True or
                receipt.get("case_id") != ASSIGNMENT + "__" + case or
                measured.get("case_id") != receipt["case_id"] or
                measured.get("map_sha256") != map_hash or
                receipt.get("physical_or_pixel_acceptance") is not False):
            raise ValueError("turn pair lacks exact independent saved-source audit: " + case)
        if (measured.get("first_junction_road_id"),
                measured.get("receiving_road_id"),
                measured.get("engineering_right_turn_observed")) != (junction, exit_road, right_seen):
            raise ValueError("turn pair did not measure requested route: " + case)
        if not (0 <= measured.get("stand_departure_frame", -1) <
                measured.get("first_intersection_entry_frame", -1) <
                measured.get("first_intersection_exit_frame", -1) < receipt.get("frames", 0)):
            raise ValueError("turn pair lacks chronological original observations")
    if (right["trace_sha256"] == straight["trace_sha256"] or
            right["capture_seal_sha256"] == straight["capture_seal_sha256"]):
        raise ValueError("turn pair reused one original attempt")
    if right["frames"] != straight["frames"]:
        raise ValueError("turn pair changed capture duration")
    right_context = right["measurement"]["context_source_joins"]
    straight_context = straight["measurement"]["context_source_joins"]
    for key in ("cab_license", "stand_designation", "stand_marking", "posted_notice",
                "jurisdiction", "designation_provisions"):
        if right_context.get(key) != straight_context.get(key):
            raise ValueError("turn pair changed fixed reviewed source: " + key)
    return {"format": "c150530-turn-pair-audit-v1", "passed": True,
            "comparison_id": "posted_right_turn_vs_straight_attempt",
            "case_ids": [ASSIGNMENT + "__" + case for case in CASES],
            "source_seal_sha256": [right["capture_seal_sha256"],
                                   straight["capture_seal_sha256"]],
            "map_sha256": map_hash,
            "observed_junction_roads": [110, 120],
            "observed_receiving_roads": [11, 12],
            "physical_or_legal_acceptance": False}


def audit(right_attempt: Path, straight_attempt: Path) -> dict:
    layouts = {case: json.loads((ROOT / "candidates" / (case + ".json")).read_text())
               for case in CASES}
    maps = {case: ROOT / "candidates" / (case + ".xodr") for case in CASES}
    inspections = {case: inspect_map(maps[case].read_bytes(), case) for case in CASES}
    if inspections[CASES[0]]["sha256"] != inspections[CASES[1]]["sha256"]:
        raise ValueError("turn pair changed fixed OpenDRIVE map")
    receipts = [audit_source_chain(attempt, case, maps[case],
                                   ROOT / "candidates" / (case + ".json"))
                for attempt, case in zip((right_attempt, straight_attempt), CASES)]
    return compare_receipts(*receipts, layouts[CASES[0]], layouts[CASES[1]],
                            inspections[CASES[0]]["sha256"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--straight-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.right_attempt, args.straight_attempt),
                                     indent=2) + "\n")


if __name__ == "__main__":
    main()
