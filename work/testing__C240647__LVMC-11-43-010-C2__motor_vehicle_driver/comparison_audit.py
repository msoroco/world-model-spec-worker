"""Reopen both original U-turn attempts and audit lane-only differences."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure
from roundabout import compare

ASSIGNMENT = "testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver"
COMPARISON = "u_turn_left_vs_outer_lane"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(left, outer, plan):
    plan = json.loads(Path(plan).read_text())
    target = next((row for row in plan["comparisons"]
                   if row["comparison_id"] == COMPARISON), None)
    if target is None or target["case_ids"] != [ASSIGNMENT + "__left_lane_u_turn",
                                                    ASSIGNMENT + "__outer_lane_u_turn"]:
        raise ValueError("exact U-turn comparison plan differs")
    a, b = measure(left), measure(outer)
    if [a["case_id"], b["case_id"]] != target["case_ids"]:
        raise ValueError("comparison attempt identities differ")
    fixture = (Path(left) / "fixture-provenance.json").is_file()
    if fixture != (Path(outer) / "fixture-provenance.json").is_file():
        raise ValueError("comparison source profiles differ")
    result = compare(a, b, expected_frames=9 if fixture else 900)
    if _sha(Path(left) / "map.json") != _sha(Path(outer) / "map.json"):
        raise ValueError("comparison source map changed")
    if a["requested_lane_observed"] is not True or b["requested_lane_observed"] is not True:
        raise ValueError("one requested allocated lane was not observed")
    if a["other_ring_lane_observed"] or b["other_ring_lane_observed"]:
        raise ValueError("original ring lane changed during a comparison member")
    if result["both_departures_observed"] is not True:
        raise ValueError("both opposite-direction U-turn departures not observed")
    return {"format": "c133321-independent-u-turn-comparison-v1",
            "comparison_id": COMPARISON, "case_ids": result["case_ids"],
            "fixed_conditions": target["fixed_conditions"],
            "deliberate_differences": target["deliberate_differences"],
            "measured": result,
            "source_hashes": {"left_map": _sha(Path(left) / "map.json"),
                              "left_history": _sha(Path(left) / "history.json"),
                              "outer_map": _sha(Path(outer) / "map.json"),
                              "outer_history": _sha(Path(outer) / "history.json")},
            "diagnostic_fixture": fixture,
            "physical_acceptance": False, "legal_lane_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--outer", type=Path, required=True)
    parser.add_argument("--comparison", default=COMPARISON)
    parser.add_argument("--comparison-id", default=ASSIGNMENT + "__" + COMPARISON)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.comparison != COMPARISON or args.comparison_id != ASSIGNMENT + "__" + COMPARISON:
        raise ValueError("exact U-turn comparison identity differs")
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    result = audit(args.left, args.outer, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
