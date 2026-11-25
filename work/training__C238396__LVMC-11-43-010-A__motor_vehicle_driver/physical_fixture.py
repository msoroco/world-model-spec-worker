"""Source-shaped CPU physical outcome and capture lifecycle fixtures."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from runner import FRAMES, RATE, RELEASE, target

ASSIGNMENT = "training__C238396__LVMC-11-43-010-A__motor_vehicle_driver"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def fixture(condition, kind):
    if condition not in RELEASE or kind not in (
            "complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown physical fixture")
    sign = RELEASE[condition]
    positions = [target("ego", frame / RATE, sign)[0] for frame in range(FRAMES)]
    if kind == "missing_evidence":
        positions.pop(300)
    elif kind == "incomplete_motion":
        positions = [positions[0]] * FRAMES
    if len(positions) != FRAMES:
        status, complete, observables = "unverified", False, {}
    else:
        cx, cy = 22.0, 0.0
        cross = sum((a[0] - cx) * (b[1] - cy) - (a[1] - cy) * (b[0] - cx)
                    for a, b in zip(positions, positions[1:]))
        complete = abs(cross) > 1000 and (cross > 0) == (sign > 0)
        status = "met" if complete else "not_met"
        observables = {"source_frames": len(positions),
                       "signed_radial_cross_sum_m2": cross} if complete else {}
    return {"format": "c238396-cpu-physical-fixture-v1",
            "case_id": ASSIGNMENT + "__" + condition,
            "kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600-frame requested position continuity and signed radial cross sum; original Native realization pending",
                "sources": ["runner.py", "native-raw-actors.jsonl",
                            "roundabout-map-readback.json"]}},
            "maneuver_completed": complete, "realized_observables": observables,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        value = {"format": "c238396-cpu-lifecycle-v1", "events": EVENTS,
                 "provenance_kind": "synthetic_fixture", "original_native_executed": False}
    else:
        value = fixture(args.condition, args.kind)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Physical fixture status differs")
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "kind": args.kind,
                      "condition": args.condition,
                      "physical_or_legal_acceptance": False}, sort_keys=True))


if __name__ == "__main__":
    main()
