"""Compare two independently sealed taxi attempts on the declared stand shift."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from candidate_comparison_audit import audit as audit_candidates
from delivery_audit import audit_source_chain
from turn_trace_finalizer import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
CASES = ("near_stand", "far_stand")


def compare_receipts(near: dict, far: dict, candidate: dict) -> dict:
    if candidate.get("passed") is not True or candidate.get("difference_m") != 20:
        raise ValueError("candidate fixed-condition comparison absent")
    for case, receipt in zip(CASES, (near, far)):
        measurement = receipt.get("measurement", {})
        if (receipt.get("format") != "c150530-saved-source-audit-v1" or
                receipt.get("passed") is not True or
                receipt.get("case_id") != ASSIGNMENT + "__" + case or
                measurement.get("case_id") != receipt["case_id"] or
                measurement.get("map_sha256") != candidate["near_map_sha256" if case == "near_stand" else "far_map_sha256"] or
                receipt.get("physical_or_pixel_acceptance") is not False):
            raise ValueError("measured comparison lacks exact independent source audit: " + case)
        if measurement.get("engineering_right_turn_observed") is not True:
            raise ValueError("measured comparison lacks first right turn: " + case)
        if (measurement.get("first_junction_road_id"),
                measurement.get("receiving_road_id")) != (110, 11):
            raise ValueError("measured comparison changed first junction or receiving road")
        if not (measurement.get("stand_departure_frame", -1) <
                measurement.get("first_intersection_entry_frame", -1) <
                measurement.get("first_intersection_exit_frame", -1) < receipt.get("frames", 0)):
            raise ValueError("measured comparison frame order incomplete")
    if near["trace_sha256"] == far["trace_sha256"] or near["capture_seal_sha256"] == far["capture_seal_sha256"]:
        raise ValueError("comparison reused the same original attempt")
    if near["frames"] != far["frames"]:
        raise ValueError("comparison changed fixed capture duration")
    fixed = ("cab_license", "jurisdiction", "designation_provisions")
    near_context = near["measurement"]["context_source_joins"]
    far_context = far["measurement"]["context_source_joins"]
    for kind in fixed:
        if near_context.get(kind) != far_context.get(kind):
            raise ValueError("comparison changed fixed reviewed context: " + kind)
    return {"format": "c150530-measured-comparison-audit-v1", "passed": True,
            "comparison_id": "stand_to_first_intersection_distance",
            "case_ids": [ASSIGNMENT + "__" + case for case in CASES],
            "source_seal_sha256": [near["capture_seal_sha256"], far["capture_seal_sha256"]],
            "authored_stand_shift_m": 20.0,
            "observed_first_junction_road_id": 110,
            "observed_receiving_road_id": 11,
            "physical_or_legal_acceptance": False}


def audit(near_attempt: Path, far_attempt: Path) -> dict:
    candidates = ROOT / "candidates"
    layouts = {case: json.loads((candidates / (case + ".json")).read_text())
               for case in CASES}
    maps = {case: (candidates / (case + ".xodr")).read_bytes() for case in CASES}
    candidate = audit_candidates(layouts["near_stand"], layouts["far_stand"],
                                 maps["near_stand"], maps["far_stand"])
    receipts = [audit_source_chain(attempt, case,
                                   candidates / (case + ".xodr"),
                                   candidates / (case + ".json"))
                for attempt, case in zip((near_attempt, far_attempt), CASES)]
    return compare_receipts(*receipts, candidate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--near-attempt", type=Path, required=True)
    parser.add_argument("--far-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.near_attempt, args.far_attempt), indent=2) + "\n")


if __name__ == "__main__":
    main()
