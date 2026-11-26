"""Saved-only exact door measurement and Core-compatible result projection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from door_measurement import measure

SOURCES = ("frame_map.json", "door.json", "activity.json", "passing_vehicle.json", "geometry.json")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _source(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_traffic_side(root: Path) -> dict:
    root = Path(root)
    config = json.loads(_source(root, "config.json").read_text())
    inventory = json.loads(_source(root, "inventory.json").read_text())
    for name in SOURCES:
        _source(root, name)
    result = measure(root, inventory, config["selected_case_id"], _source(root, "case-plan.json"))
    return {"door_side": result["door_side"],
            "passing_traffic_side": result["passing_traffic_side"],
            "door_closest_to_passing_traffic": result["door_closest_to_passing_traffic"],
            "minimum_body_clearance_m": result["minimum_body_clearance_m"],
            "open_start_frame": result["open_start_frame"]}


def measure_loading_interval(root: Path) -> dict:
    root = Path(root)
    config = json.loads(_source(root, "config.json").read_text())
    inventory = json.loads(_source(root, "inventory.json").read_text())
    for name in SOURCES:
        _source(root, name)
    result = measure(root, inventory, config["selected_case_id"], _source(root, "case-plan.json"))
    return {"activity_kind": result["activity_kind"],
            "open_duration_s": result["open_duration_s"],
            "inactive_open_duration_s": result["inactive_open_duration_s"],
            "closed_after_frame": result["closed_after_frame"],
            "legal_necessity_or_immediacy": "unresolved"}


def analyze(attempt: Path, output: Path) -> dict:
    root = Path(attempt)
    config = json.loads(_source(root, "config.json").read_text())
    construction = json.loads(_source(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("selected construction case differs")
    inventory = json.loads(_source(root, "inventory.json").read_text())
    for name in SOURCES:
        _source(root, name)
    measured = measure(root, inventory, case_id, _source(root, "case-plan.json"))
    values = {"traffic_side": measure_traffic_side(root),
              "loading_interval": measure_loading_interval(root)}
    hashes = {name: _sha(_source(root, name)) for name in SOURCES}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"traffic_side": {"method": "measure_traffic_side",
                                                "value": values["traffic_side"], "sources": hashes},
                               "loading_interval": {"method": "measure_loading_interval",
                                                    "value": values["loading_interval"], "sources": hashes}},
              "diagnostic_fixture": (root / "fixture-provenance.json").is_file(),
              "legal_verdict_claimed": False,
              "limitations": ["Door/open duration and loading activity are measurements; statutory necessity and immediacy remain unresolved.",
                              "CPU fixture is not a physical Native recording."]}
    trace = [json.loads(line) for line in _source(root, "trace.jsonl").read_text().splitlines()]
    recording = construction["recording_description"]
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=False)
    evidence = []
    channel_values = {
        "original_door_articulation": {"source_sha256": hashes["door.json"], "open_duration_s": measured["open_duration_s"]},
        "original_loading_activity": {"source_sha256": hashes["activity.json"], "inactive_open_duration_s": measured["inactive_open_duration_s"]},
        "original_passing_body_path": {"source_sha256": hashes["passing_vehicle.json"], "minimum_body_clearance_m": measured["minimum_body_clearance_m"]},
        "original_narrow_road_geometry": {"source_sha256": hashes["geometry.json"], "door_closest_to_passing_traffic": measured["door_closest_to_passing_traffic"]},
        "original_frame_map": {"source_sha256": hashes["frame_map.json"], "source_frame_count": measured["frame_count"]},
        "original_four_camera_pixels": {"source_sha256": _sha(_source(root, "video_frames.jsonl")), "view_count": 4}}
    for channel in recording["channels"]:
        name = channel["name"]
        if name not in channel_values:
            raise ValueError("unexpected exact channel: " + name)
        path = channel_dir / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": channel_values[name]}) + "\n"
                                for row in trace))
        evidence.append({"name": name, "unit": channel["unit"], "reference": str(path.relative_to(root))})
    context = channel_dir / "reviewed_narrow_road_site.json"
    context.write_text(json.dumps({"reviewed_narrow_road_site": {"geometry_sha256": hashes["geometry.json"],
                                   "legal_necessity": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_narrow_road_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound open traffic-side door and loading interval",
                                 "requested": "measured door/load relation, no legal threshold",
                                 "measured": values, "method": "measure_traffic_side/measure_loading_interval",
                                 "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Saved original review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": recording, "recording_evidence": evidence,
              "realized_observables": {}, "legal_judgment": None,
              "physical_acceptance_claimed": False}
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
