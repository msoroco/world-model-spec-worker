"""Synthetic CPU checks for stop completion and owner lifecycle ordering."""
import argparse
import json
from pathlib import Path

ASSIGNMENT = "training__C135709__NRS-484B-493__motor_vehicle_driver"
SIDES = {"controlled_1": "right", "controlled_2": "left"}
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def fixture(condition, kind):
    if condition not in SIDES or kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown physical fixture")
    side = SIDES[condition]
    y = -1.5 if side == "right" else 1.5
    samples = [{"frame": i, "x_m": 20.0, "y_m": y,
                "speed_mps": 3.0 if i < 400 else 0.0} for i in range(600)]
    if kind == "incomplete_motion":
        for sample in samples:
            sample["speed_mps"] = 3.0
    elif kind == "missing_evidence":
        samples.pop(300)
    complete = (len(samples) == 600 and all(sample["frame"] == i
                for i, sample in enumerate(samples)) and
                all(sample["speed_mps"] < .1 for sample in samples[-200:]) and
                all(18 <= sample["x_m"] <= 22 and
                    ((sample["y_m"] < 0) if side == "right" else (sample["y_m"] > 0))
                    for sample in samples[-200:]))
    status = "unverified" if len(samples) != 600 else ("met" if complete else "not_met")
    return {"format": "c135709-cpu-physical-fixture-v1",
            "case_id": ASSIGNMENT + "__" + condition,
            "kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600-frame synthetic footprint side and final 200-frame stationary continuity; original Native realization pending",
                "sources": ["vehicle-pose.jsonl", "video_frames.jsonl", "road.xodr"]}},
            "maneuver_completed": complete,
            "realized_observables": {"source_frames": len(samples), "parked_side": side,
                                     "stationary_frames": 200} if complete else {},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        value = {"format": "c135709-cpu-lifecycle-v1", "events": EVENTS,
                 "provenance_kind": "synthetic_fixture", "original_native_executed": False}
    else:
        value = fixture(args.condition, args.kind)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Physical fixture status differs")
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "kind": args.kind,
                      "condition": args.condition, "physical_or_legal_acceptance": False}, sort_keys=True))


if __name__ == "__main__":
    main()
