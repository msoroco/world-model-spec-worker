"""Saved-only motorcycle response measurement for selected flagger cases."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_original import measure_core_join


SOURCES = (
    "captured-source-hashes.json", "road.xodr", "original-flagger-review.json",
    "original-authority-source", "original-zone-source", "original-signal-source",
    "native-rows.jsonl", "video_frames.jsonl", "trace.jsonl",
    "capture/evidence.jsonl", "capture/native/frames.jsonl",
    "overview.mkv", "approach.mkv", "reference_corner.mkv",
    "driver_reference.mkv",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    measured = measure_core_join(attempt, config["case_id"])
    measured["physical_completion"] = None
    measured.pop("legal_verdict", None)
    return measured


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use fresh output")
    measured = derive(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case = config["case_id"]
    if case != construction["case_id"] or case not in config["supported_case_ids"]:
        raise ValueError("Saved flagger case identity differs")
    rows = [json.loads(line) for line in (attempt / "native-rows.jsonl").read_text().splitlines()]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row in rows:
                if name in ("motorcycle_response", "kin.velocity"):
                    value = {"position_m": row["motorcycle_xyz_m"],
                             "speed_mps": row["motorcycle_speed_mps"]}
                elif name == "drv.stopped":
                    value = row["motorcycle_speed_mps"] < 0.1
                elif name == "flagger_signal_observation":
                    value = {"requested": row["requested_signal"],
                             "visible_original_signal_reviewed": False}
                elif name == "four_view_video":
                    value = row["source_cameras"]
                else:
                    value = {"original_review_pending": True,
                             "source_frame": row["native_frame"]}
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        recording_evidence.append({"name": name, "unit": channel["unit"],
                                   "reference": "channels/" + path.name})
    review = json.loads((attempt / "original-flagger-review.json").read_text())
    for context in construction["recording_description"]["context_inputs"]:
        name = context["name"]
        if name == "flagger_authority_and_governance":
            value = {"source_review_sha256": sha(attempt / "original-flagger-review.json"),
                     "governs_approach_source": review.get("governs_approach"),
                     "independent_original_review_pending": True}
        elif name == "statutory_location_basis":
            value = {"authored_basis": review.get("statutory_location_basis"),
                     "independent_original_review_pending": True}
        else:
            raise ValueError("Unknown flagger context: " + name)
        path = channels / (name + ".json")
        path.write_text(json.dumps({name: value}) + "\n")
        recording_evidence.append({"name": name, "unit": context["unit"],
                                   "reference": "channels/" + path.name})
    from worker_exchange.native_output import write_result
    write_result(attempt, {
        "case_id": case, "measured_values": measured,
        "target_checks": [{"target": "original motorcycle response to reviewed flagger signal",
                           "requested": True, "measured": True,
                           "method": "sealed Native/Core frame and video join",
                           "tolerance": "original signal and authority review pending",
                           "matched": False, "physical_cause_confirmed": False,
                           "cause_evidence": {"source_seal_sha256":
                                              measured["source_seal_sha256"]}}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "accepted": False,
        "termination_reason": "Saved measurement only; physical and legal review pending",
        "physical_failure_flags": ["Original flagger authority and visible pixels unreviewed"],
        "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                             "driver_reference.mkv", "raw.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": recording_evidence, "realized_observables": {}})
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": {"observed_flagger_response": {
                  "method": "derive", "value": measured,
                  "sources": {name: sha(attempt / name) for name in SOURCES}}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
