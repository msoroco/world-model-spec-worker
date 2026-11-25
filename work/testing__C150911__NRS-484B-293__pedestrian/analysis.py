"""Finalize saved original crosswalk observations without deciding practicability."""

import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_delivery import measure

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(required(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    files = ("original-site.json", "original-pedestrian.jsonl",
             "original-obstacles.jsonl", "original-participants.jsonl")
    receipt = json.loads(required(root, "original-receipt.json").read_text())
    if receipt.get("case_id") != case_id or receipt.get("fps") != 20:
        raise ValueError("original crosswalk receipt identity or rate differs")
    for name in files:
        if receipt.get("sources", {}).get(name) != sha(required(root, name)):
            raise ValueError("original crosswalk source hash differs: " + name)
    site = json.loads((root / files[0]).read_text())
    samples = lines(root / files[1])
    obstacles = lines(root / files[2])
    participants = lines(root / files[3])
    if receipt.get("frame_count") != len(samples):
        raise ValueError("original frame count differs")
    measurement = measure(site, samples, obstacles, participants)
    frame_map = lines(required(root, "video_frames.jsonl"))
    graph_trace = lines(required(root, "trace.jsonl"))
    if len(frame_map) != len(samples) or len(graph_trace) != len(samples):
        raise ValueError("original crosswalk frame streams differ")
    for i, (row, mapped, graph) in enumerate(zip(samples, frame_map, graph_trace)):
        if mapped.get("video_frame") != i or mapped.get("carla_frame") != row["frame"] or (
                mapped.get("native_frame") != row["frame"] or
                graph.get("frame") != row["frame"] or
                abs(mapped.get("time_s", -1) - row["elapsed_s"]) > 1e-4):
            raise ValueError("original pedestrian frame/time join differs")
    for name in CAMERAS:
        required(root, name + ".mkv")
    description = config["case"]["recording_description"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    values = {
        "pedestrian_crosswalk_motion": lambda i: {"pedestrian_xy": samples[i]["pedestrian_xy"],
            "crosswalk_station_m": measurement["full_original_trace"][i]["station_m"],
            "right_lateral_m": measurement["full_original_trace"][i]["right_lateral_m"]},
        "right_half_space": lambda i: {"available_right_width_m": obstacles[i]["available_right_width_m"]},
        "nearby_participants": lambda i: participants[i]["participants"]}
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented crosswalk channel: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x") as stream:
            for i, row in enumerate(samples):
                stream.write(json.dumps({"time_s": row["elapsed_s"],
                    "value": values[name](i)}, separators=(",", ":")) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context = "channels/crosswalk_source.json"
    (root / context).write_text(json.dumps({"site_source_sha256":
        measurement["site_source_sha256"], "legal_practicability": "unresolved"}) + "\n")
    evidence.append({"name": "crosswalk_source", "unit": "source", "reference": context})
    native = {"case_id": case_id, "measured_values": {"crosswalk": measurement},
        "target_checks": [{"target": "source-bound pedestrian crosswalk passage",
            "requested": True, "measured": True, "method": "measure_crosswalk_passage",
            "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": list(files)}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source measurement; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    (root / "result.json").write_text(json.dumps(native, indent=2, allow_nan=False) + "\n")
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {"crosswalk_passage": {"method": "measure_crosswalk_passage",
            "sources": {name: sha(root / name) for name in files},
            "value": {"right_half_sample_count": measurement["right_half_sample_count"],
                "crosswalk_sample_count": measurement["crosswalk_sample_count"],
                "legal_practicability": "unresolved"}}},
        "limitations": ["Original site and legal practicability remain source-gated."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
