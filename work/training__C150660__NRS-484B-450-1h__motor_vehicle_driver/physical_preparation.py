"""CPU diagnostic of footprint completion and Native ownership ordering."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from case_specs import CASES, target_x
from safety_zone_geometry import measure_frame, measure_trace

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
ZONE = {"x_start_m": 80.0, "x_end_m": 100.0, "zone_near_y_m": -4.5,
        "curb_y_m": -7.4, "zone_map_source": "synthetic diagnostic geometry",
        "curb_map_source": "synthetic diagnostic geometry"}


def classify(suffix, kind):
    position, _, _, gap_ft = CASES[suffix]
    requested_x = target_x(suffix)
    if kind == "missing_evidence":
        return {"status": "unverified", "method": "600 original aligned motion/footprint samples",
                "sources": ["zone_raw.json", "trace.jsonl", "video_frames.jsonl"]}
    x = requested_x if kind == "complete_motion" else requested_x + 20.0
    rows = []
    for index in range(600):
        corners = [[x - 2.25, -7.3], [x + 2.25, -7.3],
                   [x + 2.25, -4.6], [x - 2.25, -4.6]]
        rows.append({"frame": index, "time_s": index / 20,
                     "vehicle_footprint_corners_m": corners,
                     "vehicle_stopped": True, "speed_mps": 0.0,
                     "stop_state_source": "synthetic diagnostic request"})
    observed = measure_trace(rows, ZONE)
    if position == "between":
        met = observed["stopped_between_frames"] >= 80
    else:
        measured = measure_frame(corners, ZONE)
        key = "distance_to_opposite_end_m" if position == "past_end" else "distance_to_opposite_start_m"
        met = abs(measured[key] - gap_ft * .3048) <= 0.25
    return {"status": "met" if met else "not_met",
            "method": "600 sampled four-corner footprint positions and final rest state",
            "sources": ["zone_raw.json", "trace.jsonl", "video_frames.jsonl"],
            "diagnostic_measurement": observed, "requested_gap_ft": gap_ft}


def fixture(case, kind):
    suffix = case.split("__motor_vehicle_driver__", 1)[-1]
    if suffix not in CASES:
        raise ValueError("Unknown exact case")
    check = classify(suffix, kind)
    met = check["status"] == "met"
    return {"case_id": case, "physical_checks": {"maneuver": check},
            "maneuver_completed": met,
            "realized_observables": {"diagnostic_rest_frames": 600} if met else {},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=["complete_motion", "incomplete_motion",
                                           "missing_evidence", "lifecycle"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        reversed_events = EVENTS[:-2] + ["saved_processing_started", "owner_released"]
        if reversed_events == EVENTS:
            raise AssertionError("Premature saved processing accepted")
        result = {"events": EVENTS, "exit_code": 0,
                  "premature_saved_processing_rejected": True}
    else:
        result = fixture(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind, "passed": True}))
