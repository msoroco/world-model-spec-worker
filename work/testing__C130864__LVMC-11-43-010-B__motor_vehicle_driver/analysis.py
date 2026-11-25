"""Finalize saved original roundabout sources without a legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capture_roundabout import CAMERAS
from roundabout_measurements import measure
from roundabout_delivery_audit import audit_delivery


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inputs(root):
    config = json.loads(_required(root, "config.json").read_text())
    map_path = _required(root, "original-map.json")
    trace_path = _required(root, "original-trace.jsonl")
    receipt_path = _required(root, "original-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    case_id = config["selected_case_id"]
    if receipt.get("case_id") != case_id:
        raise ValueError("saved original case identity differs")
    measurement = measure(case_id=case_id, map_path=map_path,
        trace_path=trace_path, receipt_path=receipt_path, allow_diagnostic=True)
    if not receipt.get("diagnostic_fixture"):
        audit_delivery(case_id=case_id, map_path=map_path,
                       trace_path=trace_path, receipt_path=receipt_path)
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in
                 _required(root, "video_frames.jsonl").read_text().splitlines()]
    graph_trace = [json.loads(line) for line in
                   _required(root, "trace.jsonl").read_text().splitlines()]
    if len(rows) != len(frame_map) or len(rows) != len(graph_trace):
        raise ValueError("saved original frame streams differ")
    for index, (row, mapped, graph) in enumerate(zip(rows, frame_map, graph_trace)):
        if (mapped.get("video_frame") != index or
                mapped.get("carla_frame") != row["frame"] or
                mapped.get("native_frame") != row["frame"] or
                graph.get("frame") != row["frame"] or
                abs(mapped.get("time_s", -1) - row["time_s"]) > 1e-4):
            raise ValueError("saved original frame/time join differs")
    for name in CAMERAS:
        _required(root, name + ".mkv")
    return config, measurement, rows


def _measurement(name, value, root):
    files = ("original-map.json", "original-trace.jsonl", "original-receipt.json")
    return {"method": name, "sources": {path: _sha(root / path) for path in files},
            "value": value}


def measure_roundabout_entry(root, motion):
    return _measurement("measure_roundabout_entry", {
        "first_observed_ego_entry_frame": motion["first_observed_ego_entry_frame"],
        "ego_stopped_before_entry_frames": motion["ego_stopped_before_entry_frames"]}, root)


def measure_circulating_presence(root, motion):
    return _measurement("measure_circulating_presence", {
        "opponent_circulating_lane_id": motion["opponent_circulating_lane_id"],
        "opponent_in_ring_at_ego_entry": motion["opponent_in_ring_at_ego_entry"],
        "opponent_in_conflict_at_ego_entry": motion["opponent_in_conflict_at_ego_entry"]}, root)


def measure_gap_observation(root, motion):
    return _measurement("measure_gap_observation", {
        "body_separation_at_entry_m": motion["body_separation_at_entry_m"],
        "minimum_sampled_body_separation_m": motion["minimum_sampled_body_separation_m"],
        "legal_gap_judgment": "unresolved"}, root)


def measure_lane_connectivity(root, motion):
    return _measurement("measure_lane_connectivity", {
        "entry_lane_id": motion["ego_entry_lane_id"],
        "connected_circulating_lane_id": motion["connected_circulating_lane_id"],
        "opponent_circulating_lane_id": motion["opponent_circulating_lane_id"]}, root)


def analyze(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    config, motion, rows = _inputs(root)
    case_id = config["selected_case_id"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    values = {
        "ego_roundabout_entry": lambda row: {"ego_vertices": row["ego_vertices"],
                                               "ego_speed_mps": row["ego_speed_mps"]},
        "circulating_vehicle_presence": lambda row: {"opponent_vertices": row["opponent_vertices"],
            "opponent_speed_mps": row["opponent_speed_mps"]},
        "entry_conflict_motion": lambda row: {"ego_vertices": row["ego_vertices"],
            "opponent_vertices": row["opponent_vertices"]},
        "observed_preentry_gap": lambda row: {"ego_speed_mps": row["ego_speed_mps"],
            "opponent_speed_mps": row["opponent_speed_mps"]}}
    description = config["case"]["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented selected channel: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"],
                    "value": values[name](row)}, separators=(",", ":"),
                    allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context = "channels/reviewed_roundabout_source.json"
    (root / context).write_text(json.dumps({"reviewed_roundabout_source": {
        "map_packet_sha256": motion["source_bindings"]["map_packet_sha256"],
        "legal_gap_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_roundabout_source", "unit": "source",
                     "reference": context})
    native = {"case_id": case_id, "measured_values": {"motion": motion},
        "target_checks": [{"target": "source-bound roundabout entry and circulating vehicle",
            "requested": True, "measured": True, "method": "measure_roundabout_entry",
            "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["original-map.json", "original-trace.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source measurement; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    (root / "result.json").write_text(json.dumps(native, indent=2,
        allow_nan=False) + "\n")
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {"roundabout_entry": measure_roundabout_entry(root, motion),
            "circulating_presence": measure_circulating_presence(root, motion),
            "gap_observation": measure_gap_observation(root, motion),
            "lane_connectivity": measure_lane_connectivity(root, motion)},
        "limitations": ["Original site and legal traffic gap remain source-gated."]}
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
