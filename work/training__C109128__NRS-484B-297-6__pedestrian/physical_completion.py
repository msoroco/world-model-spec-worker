"""Source-bound sidewalk bypass completion check; no legal finding."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from finalize import original_measurement

REQUIRED = ("config.json", "sidewalk_context.json", "pedestrian-original.jsonl",
            "video_frames.jsonl", "camera-sources.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(attempt):
    root = Path(attempt)
    source_hashes = {name: sha(root / name) for name in REQUIRED
                     if (root / name).is_file()}
    missing = sorted(set(REQUIRED) - set(source_hashes))
    status = "unverified"
    measured = {}
    reason = "missing source: " + ", ".join(missing) if missing else ""
    if not missing:
        try:
            measured = original_measurement(root)
        except ValueError as error:
            reason = str(error)
            if reason == "No original road entry and full sidewalk return":
                status = "not_met"
        else:
            if (measured["first_road_footprint_frame"] <
                    measured["first_full_sidewalk_return_frame"] and
                    measured["road_footprint_frames"] > 0):
                status = "met"
            else:
                status = "not_met"
                reason = "No measured road entry followed by full sidewalk return"
    check = {"status": status,
             "method": "600 original pedestrian footprints joined to map and four camera frame sources; geometric motion only",
             "sources": source_hashes,
             "missing_evidence": missing,
             "details": {"reason": reason, "legal_verdict_claimed": False,
                         "physical_causation_claimed": False}}
    return {"physical_checks": {"maneuver": check},
            "maneuver_completed": status == "met",
            "realized_observables": ({"geometric_bypass": measured} if status == "met" else {}),
            "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True,
            "legal_verdict_claimed": False,
            "physical_acceptance_claimed": False}


def validate_lifecycle(events):
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected:
        raise ValueError("Saved processing preceded Native closure or owner release")
    return expected


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = assess(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"maneuver": result["physical_checks"]["maneuver"]["status"],
                      "scope": "synthetic fixture only"}))
