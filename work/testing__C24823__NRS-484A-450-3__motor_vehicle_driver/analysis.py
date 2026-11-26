"""Saved-only original yield-reference analysis; legal judgments stay unresolved."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from yield_measure import measure, require
from yield_source import CAMERAS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _record(name, value, root):
    names = ("original-yield-site.json", "original-yield-trace.jsonl", "original-yield-receipt.json")
    return {"method": name, "sources": {item: _sha(root / item) for item in names}, "value": value}


def measure_reference_hierarchy(root, data):
    return _record("measure_reference_hierarchy", {
        "reference_kind": data["reference"]["reference_kind"],
        "reference_position": data["reference"]["reference_position"],
        "selected_candidate_id": data["reference"]["selected_candidate_id"]}, root)


def measure_original_view(root, data):
    return _record("measure_original_view", {
        "geometric_view_candidate": data["reference"]["selected_candidate_id"],
        "original_driver_view_confirmed": False,
        "source": data["source_bindings"]["original-yield-site.json"]}, root)


def measure_stop_behavior(root, data):
    return _record("measure_stop_behavior", {
        "stop_samples": data["original_stop_samples"],
        "sample_count": data["original_sample_count"],
        "safety_necessity_source": data["safety_necessity_source"],
        "legal_stopping_assessment": None}, root)


def analyze(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(require(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    receipt = json.loads(require(root, "original-yield-receipt.json").read_text(encoding="utf-8"))
    data = measure(root, case_id)
    rows = [json.loads(line) for line in require(root, "original-yield-trace.jsonl").read_text().splitlines()]
    mapped = [json.loads(line) for line in require(root, "video_frames.jsonl").read_text().splitlines()]
    graph = [json.loads(line) for line in require(root, "trace.jsonl").read_text().splitlines()]
    if len(rows) != len(mapped) or len(rows) != len(graph):
        raise ValueError("saved original yield graph/frame/vehicle streams differ")
    for index, (row, frame, sample) in enumerate(zip(rows, mapped, graph)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != row["frame"] or
                frame.get("native_frame") != row["frame"] or sample.get("frame") != row["frame"] or
                abs(frame.get("time_s", -1) - row["time_s"]) > 1e-4):
            raise ValueError("saved original yield frame/time join differs")
    for name in CAMERAS:
        require(root, name + ".mkv")
    if not receipt.get("diagnostic_fixture"):
        from delivery_audit import audit
        audit(root, case_id)
    description = config["case"]["recording_description"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    bindings = {
        "original_body_polygon": lambda row: row["ego_vertices"],
        "original_speed": lambda row: row["ego_speed_mps"],
        "yield_control_readback": lambda row: row.get("yield_control_readback", {}),
        "original_view_geometry": lambda row: {"reference": data["reference"],
            "actual_driver_view_confirmed": False},
        "four_camera_frames": lambda row: row["camera_frames"]}
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in bindings:
            raise ValueError("unimplemented original yield channel: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": bindings[name](row)},
                    separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context = "channels/reviewed_yield_context.json"
    (root / context).write_text(json.dumps({"reviewed_yield_context": {
        "reference": data["reference"],
        "safety_necessity_source": data["safety_necessity_source"],
        "legal_judgment": None}}) + "\n")
    evidence.append({"name": "reviewed_yield_context", "unit": "source", "reference": context})
    native = {"case_id": case_id, "measured_values": {"yield_reference_and_stop": data},
        "target_checks": [{"target": "source-selected yield stopping reference and observed stop trace",
            "requested": config["requested_stop_behavior"],
            "measured": {"reference_kind": data["reference"]["reference_kind"],
                "stop_sample_count": len(data["original_stop_samples"])},
            "method": "yield_measure.measure", "tolerance": 0,
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": ["original-yield-site.json", "original-yield-trace.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved original-source measurement; physical and legal review pending",
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
            check["missing_evidence"] = ["reviewed original Native yield approach and physical acceptance"]
        native["setup_confirmed"] = native["behavior_attempted"] = native["maneuver_completed"] = False
    validate_result(native)
    (root / "result.json").write_text(json.dumps(native, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {"reference_hierarchy": measure_reference_hierarchy(root, data),
            "original_view": measure_original_view(root, data),
            "stop_behavior": measure_stop_behavior(root, data)},
        "limitations": data["limitations"]}
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
