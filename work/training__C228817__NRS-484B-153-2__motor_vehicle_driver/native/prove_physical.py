"""CPU-only diagnostic of measured door motion and capture ownership order.

These fixtures exercise decisions over synthetic reviewed sources. They never
represent observation from a live Native run or a legal determination.
"""

import argparse
import hashlib
import json
from pathlib import Path


ORDER = ["capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def lifecycle(events):
    if events != ORDER:
        raise ValueError("saved processing precedes Native ownership closure")
    return True


def evaluate(attempt, kind):
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    trace_path = attempt / "native-door-trace.jsonl"
    frame_path = attempt / "video_frames.jsonl"
    trace, frames = rows(trace_path), rows(frame_path)
    if len(trace) != 600 or len(frames) != 600:
        raise ValueError("synthetic source frame history incomplete")
    review_path = attempt / "door-pixel-review.json"
    if kind == "missing_evidence":
        review = None
    else:
        review = json.loads(review_path.read_text())
        if review.get("case_id") != config["case_id"] or len(review["door_observations"]) != 600:
            raise ValueError("review differs from diagnostic source")
    sources = {"native-door-trace.jsonl": sha(trace_path),
               "video_frames.jsonl": sha(frame_path)}
    if review is not None:
        sources["door-pixel-review.json"] = sha(review_path)
    if kind == "complete_motion":
        opened = [i for i, row in enumerate(review["door_observations"])
                  if row["door_open"]]
        if not opened or not review["transfer_events"]:
            raise ValueError("complete fixture lacks observed door and transfer")
        first, last = opened[0], opened[-1]
        if first != 100 or last != 211:
            raise ValueError("reviewed synthetic door interval differs")
        if review["observed_door_side"] != review["observed_traffic_side"]:
            raise ValueError("reviewed synthetic passing side differs")
        moving = [i for i, row in enumerate(trace) if row.get("passing_speed_mps", 0) > 0.05]
        if len(moving) != 101 or not all(trace[i].get("passing_lateral_offset_m", 0) > 0.25 for i in moving):
            raise ValueError("moving same-side passing traffic source missing")
        if review["transfer_events"][0].get("occupancy_delta_observed") != config["occupancy_delta_requested"]:
            raise ValueError("boarding or alighting source differs")
        status = "met"
        observables = {"reviewed_open_frames": len(opened),
                       "reviewed_open_interval_s": [first / 20, (last + 1) / 20],
                       "reviewed_transfer_events": len(review["transfer_events"]),
                       "reviewed_traffic_side": review["observed_traffic_side"],
                       "moving_passing_frames": len(moving)}
    elif kind == "incomplete_motion":
        # Controlled diagnostic: the saved review is present, but a complete
        # door opening is removed from the reviewed observation sequence.
        observed = [False for _ in review["door_observations"]]
        status = "not_met" if not any(observed) else "met"
        observables = {"reviewed_open_frames": sum(observed),
                       "fixture_change": "all reviewed door-open observations suppressed"}
    elif kind == "missing_evidence":
        status = "unverified"
        observables = {}
    else:
        raise ValueError("unknown fixture kind")
    return {"case_id": config["case_id"], "fixture_kind": kind,
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False,
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "reviewed synthetic door pixels and frame/time joins; controlled missing/incomplete mutations",
                "sources": sources}},
            "maneuver_completed": status == "met",
            "realized_observables": observables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output")
    parser.add_argument("--lifecycle", action="store_true")
    args = parser.parse_args()
    if args.lifecycle:
        assert lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + [ORDER[-1], ORDER[-2]])
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError("premature saved processing accepted")
        print("complete capture ownership lifecycle and premature saved processing rejected")
    else:
        result = evaluate(args.attempt, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(args.kind, result["physical_checks"]["maneuver"]["status"])
