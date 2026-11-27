"""Synthetic maneuver and ownership-order proof; not original physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import measure, rows


ORDER = ("capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events):
    if tuple(events) != ORDER:
        raise ValueError("saved processing precedes Native ownership closure")
    return True


def evaluate(attempt, kind):
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    case = config["case_id"]
    trace_path = attempt / "emergency-native.jsonl"
    frame_path = attempt / "video_frames.jsonl"
    trace, frames = rows(trace_path), rows(frame_path)
    if len(trace) != len(frames) or len(trace) != 600 or any(
            t["native_frame"] != f["native_frame"] or t["frame"] != f["video_frame"]
            for t, f in zip(trace, frames)):
        raise ValueError("Synthetic original frame joins incomplete")
    sources = {"emergency-native.jsonl": sha(trace_path),
               "video_frames.jsonl": sha(frame_path)}
    if kind == "missing_evidence":
        status, observables = "unverified", {}
    else:
        measurement = measure(attempt, case, diagnostic=True)
        suffix = case[-2:]
        if suffix == "01":
            expected = bool(measurement["active_nonadjacent_frames"])
        elif suffix == "03":
            expected = any(row.get("traffic") for row in trace) and any(
                row.get("weather_precipitation", 0) > 0 for row in trace)
        elif suffix == "04":
            expected = bool(measurement["visible_hand_signal_frames"])
        elif suffix == "05":
            expected = bool(measurement["visible_officer_direction_frames"])
        else:
            expected = bool(measurement["active_adjacent_frames"])
        status = ("met" if expected else "not_met") if kind == "complete_motion" else "not_met"
        observables = {"active_approach_frames": len(measurement["active_approach_frames"]),
                       "active_adjacent_frames": len(measurement["active_adjacent_frames"]),
                       "active_nonadjacent_frames": len(measurement["active_nonadjacent_frames"]),
                       "source_branch": suffix,
                       "original_native_observed": False}
        sources.update(measurement["source_sha256"])
    return {"case_id": case, "fixture_kind": kind,
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False,
            "physical_checks": {"maneuver": {"status": status,
                "method": "synthetic source-joined emergency approach, lane and conditional branch with controlled incomplete/missing mutations",
                "sources": sources}},
            "maneuver_completed": status == "met",
            "realized_observables": observables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                           "missing_evidence"))
    parser.add_argument("--output")
    parser.add_argument("--lifecycle", action="store_true")
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + (ORDER[-1], ORDER[-2]))
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError("Premature saved processing accepted")
        print("capture ownership closure precedes saved processing")
    else:
        result = evaluate(args.attempt, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(args.kind, result["physical_checks"]["maneuver"]["status"])
