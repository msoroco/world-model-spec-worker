"""Project source-sealed original island passage into saved evidence; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from island_measurements import measure
from island_source import CAMERAS


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _measurement(name, value, root):
    files = ("original-map.json", "original-trace.jsonl", "original-receipt.json")
    return {"method": name, "sources": {item: _sha(root / item) for item in files},
            "value": value}


def measure_island_passage(root, motion):
    return _measurement("measure_island_passage", motion, root)


def measure_side_observation(root, motion):
    return _measurement("measure_side_observation", {
        "sampled_right_of_island_frames": motion["sampled_right_of_island_frames"],
        "sampled_left_or_overlap_frames": motion["sampled_left_or_overlap_frames"],
        "continuous_between_frames": "unverified"}, root)


def measure_lane_connectivity(root, motion):
    return _measurement("measure_lane_connectivity", {
        "lane_roles": sorted({obs["lane_role"] for obs in motion["observations"]}),
        "observed_lane_ids": sorted({obs["ego_lane_id"] for obs in motion["observations"]})}, root)


def analyze(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(_required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    receipt_path = _required(root, "original-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("case_id") != case_id:
        raise ValueError("saved original case identity differs")
    if not receipt.get("diagnostic_fixture"):
        from delivery_audit import audit
        audit(root, case_id)
    measurement = measure(case_id=case_id, map_path=_required(root, "original-map.json"),
        trace_path=_required(root, "original-trace.jsonl"), receipt_path=receipt_path,
        allow_diagnostic=True)
    rows = [json.loads(line) for line in _required(root, "original-trace.jsonl").read_text().splitlines()]
    frame_map = [json.loads(line) for line in _required(root, "video_frames.jsonl").read_text().splitlines()]
    graph = [json.loads(line) for line in _required(root, "trace.jsonl").read_text().splitlines()]
    if len(rows) != len(frame_map) or len(rows) != len(graph):
        raise ValueError("saved original graph/frame/vehicle streams differ")
    for index, (row, mapped, sample) in enumerate(zip(rows, frame_map, graph)):
        if (mapped.get("video_frame") != index or mapped.get("carla_frame") != row["frame"] or
                mapped.get("native_frame") != row["frame"] or sample.get("frame") != row["frame"] or
                abs(mapped.get("time_s", -1) - row["time_s"]) > 1e-4):
            raise ValueError("saved original frame/time join differs")
    for name in CAMERAS:
        _required(root, name + ".mkv")
    description = config["case"]["recording_description"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    data = {
        "original_body_polygon": lambda row: row["ego_vertices"],
        "original_heading": lambda row: row["ego_heading"],
        "observed_lane": lambda row: row["ego_lane_id"],
        "island_side_and_overlap": lambda row: next(
            obs for obs in measurement["observations"] if obs["frame"] == row["frame"]),
        "four_camera_frames": lambda row: row.get("camera_frames", {}),
    }
    for channel in description["channels"]:
        name = channel["name"]
        if name not in data:
            raise ValueError("unimplemented original island channel: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": data[name](row)},
                    separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context = "channels/reviewed_island_context.json"
    (root / context).write_text(json.dumps({"reviewed_island_source": {
        "map_packet_sha256": measurement["source_bindings"]["map_packet_sha256"],
        "native_map_sha256": measurement["source_bindings"]["native_map_sha256"],
        "legal_judgment": "unresolved"}}) + "\n", encoding="utf-8")
    evidence.append({"name": "reviewed_island_source", "unit": "source", "reference": context})
    native = {"case_id": case_id, "measured_values": {"island_passage": measurement},
        "target_checks": [{"target": "sampled right-of-rotary-island passage",
            "requested": config["requested_island_side"],
            "measured": {"sampled_right_frames": measurement["sampled_right_of_island_frames"],
                         "sampled_left_or_overlap_frames": measurement["sampled_left_or_overlap_frames"]},
            "method": "island_measurements.measure", "tolerance": 0,
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": ["original-map.json", "original-trace.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved source measurement; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}, "legal_judgment": None,
        "physical_acceptance_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result
    native = physical_result(root, native)
    if receipt.get("diagnostic_fixture"):
        for check in native["physical_checks"].values():
            check["status"] = "unverified"
            check["missing_evidence"] = ["reviewed original Native island passage and physical acceptance"]
        native["setup_confirmed"] = False
        native["behavior_attempted"] = False
        native["maneuver_completed"] = False
    validate_result(native)
    (root / "result.json").write_text(json.dumps(native, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {
            "island_passage": measure_island_passage(root, measurement),
            "side_observation": measure_side_observation(root, measurement),
            "lane_connectivity": measure_lane_connectivity(root, measurement)},
        "limitations": ["Sampled geometry cannot prove between-frame continuity or legal right-of-island judgment.",
                        "Diagnostic fixture cannot establish original physical acceptance."]}
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
