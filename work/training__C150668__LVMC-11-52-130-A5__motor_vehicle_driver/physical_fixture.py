"""Bounded synthetic stop and capture-lifecycle fixture checks."""
import argparse
import json
from pathlib import Path

ASSIGNMENT = "training__C150668__LVMC-11-52-130-A5__motor_vehicle_driver"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
TARGETS = {"probe_1": 10.0, "probe_2": 5.0, "probe_3": 1.0,
           "probe_4": 5.0, "probe_5": 5.0, "probe_6": 5.0,
           "probe_7": 5.524}


def fixture(condition, kind):
    if condition not in TARGETS or kind not in (
            "complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown physical fixture")
    target = TARGETS[condition]
    samples = [{"frame": i, "x_m": target,
                "speed_mps": 3.0 if i < 100 else 0.0} for i in range(600)]
    if kind == "incomplete_motion":
        for sample in samples:
            sample["speed_mps"] = 3.0
    elif kind == "missing_evidence":
        samples.pop(300)
    complete = (len(samples) == 600 and
                all(sample["frame"] == i for i, sample in enumerate(samples)) and
                all(sample["speed_mps"] <= .1 and
                    abs(sample["x_m"] - target) < 1e-9 for sample in samples[-200:]))
    status = "unverified" if len(samples) != 600 else (
        "met" if complete else "not_met")
    return {"format": "c150668-cpu-physical-fixture-v1",
            "case_id": ASSIGNMENT + "__" + condition, "kind": kind,
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600 joined synthetic frames and final 200 stationary body positions at requested station",
                "sources": ["vehicle-poses.jsonl", "video_frames.jsonl", "road.xodr"]}},
            "maneuver_completed": complete,
            "realized_observables": {"source_frames": 600,
                "stationary_frames": 500, "requested_station_m": target}
                if complete else {},
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        value = {"format": "c150668-cpu-lifecycle-v1", "events": EVENTS,
                 "provenance_kind": "synthetic_fixture",
                 "original_native_executed": False}
    else:
        value = fixture(args.condition, args.kind)
        if value["physical_checks"]["maneuver"]["status"] != {
                "complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]:
            raise ValueError("Physical fixture status differs")
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "kind": args.kind,
                      "condition": args.condition,
                      "physical_or_legal_acceptance": False}))


if __name__ == "__main__":
    main()
