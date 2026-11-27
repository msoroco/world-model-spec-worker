"""Saved-only source-bound walking measurement and Native result writer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from walking_measure import measure

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def measure_walking_source(packet: dict) -> dict:
    return measure(packet)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def analyze(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    config = json.loads(required(attempt, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    source = required(attempt, "original-walking-observations.json")
    receipt_path = required(attempt, "original-walking-receipt.json")
    packet = json.loads(source.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if packet.get("case_id") != case_id or receipt.get("case_id") != case_id or receipt.get("source_sha256") != sha(source) or receipt.get("fps") != 20:
        raise ValueError("original walking source receipt identity or hash differs")
    if packet.get("diagnostic_fixture") is False and packet.get("original_trace_id") != "Native:" + sha(required(attempt, "trace.jsonl")):
        raise ValueError("original walking trace source differs")
    if packet.get("diagnostic_fixture") is False:
        reviewed = json.loads(required(attempt, "reviewed-site-receipt.json").read_text(encoding="utf-8"))
        if reviewed.get("packet", {}).get("sha256") != packet.get("site_source_sha256"):
            raise ValueError("reviewed original site packet hash differs")
        for item in [reviewed["packet"], *reviewed.get("sources", {}).values()]:
            if sha(required(attempt, item["path"])) != item.get("sha256"):
                raise ValueError("reviewed original source hash differs")
    measurement = measure_walking_source(packet)
    frames = packet["frames"]
    frame_map = rows(required(attempt, "video_frames.jsonl"))
    trace = rows(required(attempt, "trace.jsonl"))
    if receipt.get("frame_count") != len(frames) or len(frames) != len(frame_map) or len(frames) != len(trace):
        raise ValueError("original walking frame count or stream join differs")
    for index, (frame, mapped, row) in enumerate(zip(frames, frame_map, trace)):
        if (mapped.get("video_frame") != index or frame.get("frame") != mapped.get("carla_frame")
                or frame.get("frame") != mapped.get("native_frame") or row.get("frame") != frame.get("frame")
                or abs(frame["time_s"] - mapped.get("time_s", -1)) > 1e-4
                or abs(frame["time_s"] - row.get("time_s", -1)) > 1e-4):
            raise ValueError("original walking frame/time join differs")
    for camera in CAMERAS:
        required(attempt, camera + ".mkv")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    description = config["case"]["recording_description"]
    values = {"pedestrian_motion": lambda frame: {"pedestrian_xyz_m": frame["pedestrian_xyz_m"], "pedestrian_forward_xy": frame["pedestrian_forward_xy"]},
              "approaching_traffic": lambda frame: {"vehicle_xyz_m": frame["vehicle_xyz_m"], "vehicle_forward_xy": frame["vehicle_forward_xy"]}}
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented walking channel: " + name)
        ref = "channels/" + name + ".jsonl"
        with (attempt / ref).open("x", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps({"time_s": frame["time_s"], "value": values[name](frame)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": ref})
    context = "channels/public_highway_and_sidewalk.json"
    (attempt / context).write_text(json.dumps({"public_highway_and_sidewalk": {"site": packet["site"], "site_source_sha256": packet["site_source_sha256"]}}) + "\n", encoding="utf-8")
    evidence.append({"name": "public_highway_and_sidewalk", "unit": "source", "reference": context})
    native = {"case_id": case_id, "measured_values": {"walking_side_and_facing": measurement},
              "target_checks": [{"target": "source-bound original walking along highway", "requested": True,
                                 "measured": measurement["pedestrian_progress_m"], "method": "measure_walking_source",
                                 "tolerance": None, "matched": None, "physical_cause_confirmed": False,
                                 "cause_evidence": ["original-walking-observations.json"]}],
              "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source measurement; physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [camera + ".mkv" for camera in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
              "recording_evidence": evidence, "realized_observables": {}}
    (attempt / "result.json").write_text(json.dumps(native, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"walking_side_and_facing": {"method": "measure_walking_source", "sources": {
                  "original-walking-observations.json": sha(source),
                  "original-walking-receipt.json": sha(receipt_path)}, "value": measurement}},
              "limitations": ["Original map/public status and actual motion require independent review; no legal verdict or physical acceptance from software fixture."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
