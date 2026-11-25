"""Saved-only C109137 crossing diagnostic, with original-source path preserved."""
import argparse
import hashlib
import json
from pathlib import Path

from saved import process

SOURCES = ("native-raw-actors.jsonl", "video_frames.jsonl", "review.json",
           "trace.jsonl", "capture/evidence.jsonl")
VIDEOS = ("overview.mkv", "forward.mkv", "stripe_side.mkv", "rear.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_adjoining_crossing(metric):
    return {"first_stripe_body_frame": metric["first_observed_stripe_frame"],
            "first_adjoining_road_frame": metric["first_adjoining_lane_frame"],
            "first_left_indicator_frame": metric["first_observed_signal_frame"],
            "observed_signal_lead_s": metric["observed_signal_lead_s"],
            "minimum_other_traffic_speed_mps": metric["minimum_other_traffic_speed_mps"],
            "zone_designation_verified": False,
            "no_impediment_legally_established": False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain previous analysis; use a fresh attempt")
    for name in (*SOURCES, *VIDEOS, "config.json", "construction.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    cfg = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = cfg["case_id"]
    if (case_id != construction["case_id"] or
            case_id != "training__C109137__NRS-484B-217-2__motor_vehicle_driver__probe_1"):
        raise ValueError("Exact crossing case differs")
    reviewed = json.loads((attempt / "review.json").read_text())
    synthetic = reviewed.get("source_kind") == "synthetic_fixture"
    metric = process(attempt, attempt / "native-raw-actors.jsonl",
                     attempt / "video_frames.jsonl", attempt / "review.json",
                     synthetic=synthetic)
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"adjoining_crossing": {
                  "method": "measure_adjoining_crossing",
                  "value": measure_adjoining_crossing(metric),
                  "sources": source_hashes}},
              "diagnostic_fixture": synthetic,
              "physical_or_legal_acceptance": False}
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame in frames:
                stream.write(json.dumps({"time_s": frame["time_s"],
                                         "value": measure_adjoining_crossing(metric)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    result = {"case_id": case_id,
              "measured_values": measure_adjoining_crossing(metric),
              "target_checks": [{"target": "observed adjoining-road crossing",
                                 "requested": True,
                                 "measured": metric["first_adjoining_lane_frame"] is not None,
                                 "method": "saved Native road and body review",
                                 "tolerance": 0,
                                 "matched": metric["first_adjoining_lane_frame"] is not None,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(SOURCES)}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "600-frame saved source diagnostic",
              "physical_failure_flags": ["Original zone and no-impediment review pending"],
              "trace_reference": "trace.jsonl",
              "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": {},
              "provenance_kind": "synthetic_local_diagnostic" if synthetic else "original_native",
              "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
