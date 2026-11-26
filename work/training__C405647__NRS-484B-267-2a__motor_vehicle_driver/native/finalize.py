"""Saved-only speed analysis for the selected moving emergency-vehicle pair."""
import argparse
import hashlib
import json
from pathlib import Path

from observed_speed import measure

VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
SOURCES = ("emergency_observations.jsonl", "video_frames.jsonl", "trace.jsonl",
           "capture/manifest.json", "acquisition-provenance.json", *VIDEOS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_speed_response(measured):
    return {"speed_before_mps": measured["speed_before_mps"],
            "speed_after_mps": measured["speed_after_mps"],
            "reduction_mps": measured["reduction_mps"],
            "first_pass_frame": measured["first_pass_frame"],
            "reasonable_and_proper_legally_determined": False}


def measure_approach_setup(measured):
    return {"approach_and_pass_observed_in_source_rows": True,
            "first_pass_frame": measured["first_pass_frame"],
            "flashing_state_transitions_observed_in_source_rows": True,
            "authorization_and_lamp_qualification_visual_review_pending": True,
            "officer_exception_independently_reviewed": False}


def measure_reviewed_scope(measured):
    return {"first_pass_frame": measured["first_pass_frame"],
            "original_camera_review_pending": True,
            "original_physical_acceptance_claimed": False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior finalization; use a fresh attempt")
    for name in (*SOURCES, "config.json", "construction.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    if config.get("case_id") != construction.get("case_id"):
        raise ValueError("Saved case identity differs")
    synthetic = provenance.get("diagnostic_fixture") is True
    if not synthetic:
        if provenance.get("provenance_kind") != "native" or not (attempt / "capture-seal.json").is_file():
            raise ValueError("Original Native capture seal missing")
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    measured = measure(attempt / "emergency_observations.jsonl", synthetic=synthetic)
    observations = [json.loads(line) for line in
                    (attempt / "emergency_observations.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(mapping) != 600 or any(mapping[i].get("native_frame") != row.get("native_frame")
                                   or mapping[i].get("video_frame") not in (None, i)
                                   or abs(mapping[i].get("time_s", -1) - row["time_s"]) > 1e-6
                                   for i, row in enumerate(observations)):
        raise ValueError("Saved Native frame map differs")
    channel = attempt / "emergency_speed_and_lamps.jsonl"
    channel_rows = []
    for row in observations:
        value = {"ego_speed_mps": row["ego"]["speed_mps"],
                 "emergency_speed_mps": row["qualifying_vehicle"]["speed_mps"],
                 "flashing_state": row["qualifying_vehicle"]["flashing_state"]}
        channel_rows.append(json.dumps({"time_s": row["time_s"], "value": value},
                                       allow_nan=False) + "\n")
    expected_channel = "".join(channel_rows)
    if channel.exists():
        if channel.read_text() != expected_channel:
            raise ValueError("Saved derived channel differs from original observations")
    else:
        with channel.open("x") as stream:
            stream.write(expected_channel)
    response = measure_speed_response(measured)
    report = {"format": "c405647-saved-speed-analysis-v1", "case_id": config["case_id"],
              "measurements": {"approach_setup": {"method": "measure_approach_setup",
                                                    "value": measure_approach_setup(measured),
                                                    "sources": source_hashes},
                               "speed_response": {"method": "measure_speed_response",
                                                  "value": response, "sources": source_hashes},
                               "reviewed_scope": {"method": "measure_reviewed_scope",
                                                  "value": measure_reviewed_scope(measured),
                                                  "sources": source_hashes}},
              "fixture_only": synthetic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    requested = config["ego_target_speed_mps"]
    result = {"case_id": config["case_id"], "measured_values": response,
              "target_checks": [{"target": "ego speed engineering request",
                                 "requested": requested,
                                 "measured": response["speed_after_mps"],
                                 "method": "original saved actor velocity and frame/time join",
                                 "tolerance": 0.5,
                                 "matched": abs(requested - response["speed_after_mps"]) <= 0.5,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(SOURCES)}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "600-frame saved diagnostic completed; original qualification review pending",
              "physical_failure_flags": ["Lamp qualification, original pixels and reasonable-speed judgment require review"],
              "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": [{"name": "emergency_speed_and_lamps", "unit": "structured",
                                      "reference": "emergency_speed_and_lamps.jsonl"}],
              "realized_observables": {}, "provenance_kind": "synthetic_local_diagnostic" if synthetic else "original_native",
              "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    if any(sha(attempt / name) != source_hashes[name] for name in SOURCES):
        raise ValueError("Saved analysis rewrote original acquisition")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
