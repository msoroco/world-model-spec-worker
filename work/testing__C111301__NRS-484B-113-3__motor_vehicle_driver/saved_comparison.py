"""Replay the pedestrian backing comparison from two sealed Native attempts."""
import argparse
import json
from pathlib import Path

from backing_measurements import compare
from saved_backing import ASSIGNMENT, process


YIELD = ASSIGNMENT + "__pedestrian_yield"
CONTINUE = ASSIGNMENT + "__pedestrian_continue"


def audit(yield_attempt, continue_attempt):
    left = process(yield_attempt, YIELD)
    right = process(continue_attempt, CONTINUE)
    if Path(yield_attempt).resolve() == Path(continue_attempt).resolve():
        raise ValueError("comparison requires distinct attempts")
    left_acq = json.loads((Path(yield_attempt) / "acquisition.json").read_text(encoding="utf-8"))
    right_acq = json.loads((Path(continue_attempt) / "acquisition.json").read_text(encoding="utf-8"))
    if left_acq["map_packet"]["sha256"] != right_acq["map_packet"]["sha256"]:
        raise ValueError("fixed original map, routes, blueprints or control differ")
    if [r["time_s"] for r in left["measurement"]["frames"]] != [r["time_s"] for r in right["measurement"]["frames"]]:
        raise ValueError("fixed original time window differs")
    measured = compare(left["measurement"], right["measurement"])
    return {"format": "saved-backing-comparison-v1", "assignment_id": ASSIGNMENT,
            "comparison_id": "pedestrian_yield_response", "case_ids": [YIELD, CONTINUE],
            "attempt_acquisition_sha256": [left["acquisition_sha256"], right["acquisition_sha256"]],
            "fixed_map_packet_sha256": left_acq["map_packet"]["sha256"],
            "source_ids": measured["sources"], "frame_count": left["frame_count"],
            "fixed_observables": measured["fixed_observables"] + ["time_s", "map_packet"],
            "changed_observables": measured["changed_observables"],
            "physical_completion": False, "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yield-attempt", required=True)
    parser.add_argument("--continue-attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.yield_attempt, args.continue_attempt)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
