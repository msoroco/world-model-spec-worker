"""Synthetic maneuver and ownership-order proof; not original physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import measure_saved, rows


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
        measurement = measure_saved(attempt, case, diagnostic=True)['measurement']
        suffix = case[-2:]
        expected = bool(measurement['first_passing_frame'] >
                        measurement['first_approach_frame'])
        if suffix == '03':
            expected &= measurement['qualifying_role'] == 'official_regulatory'
        if suffix == '04':
            expected &= measurement['activation_mode'] == 'visible_hand_signal'
        if suffix == '05':
            expected &= 'proceed' in measurement['officer_direction_states']
        status = ("met" if expected else "not_met") if kind == "complete_motion" else "not_met"
        observables = {"first_approach_frame": measurement['first_approach_frame'],
                       "first_passing_frame": measurement['first_passing_frame'],
                       "ego_speed_at_first_pass_mps": measurement['ego_speed_at_first_pass_mps'],
                       "minimum_passing_surface_gap_m": measurement['minimum_passing_surface_gap_m'],
                       "source_branch": suffix,
                       "original_native_observed": False}
        sources.update(measure_saved(attempt, case, diagnostic=True)["source_sha256"])
    return {"case_id": case, "fixture_kind": kind,
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False,
            "physical_checks": {"maneuver": {"status": status,
                "method": "synthetic source-joined emergency approach, speed/clearance and conditional branch with controlled incomplete/missing mutations",
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
