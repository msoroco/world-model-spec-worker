"""Saved-only source-bound U-turn lane and departure measurement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from roundabout import SourceError, load_sealed_json, verify_original_history, verify_topology

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    construction = json.loads(_required(root, "construction.json").read_text())
    case = config["selected_case_id"]
    if construction["case_id"] != case:
        raise ValueError("selected construction case differs")
    inventory = json.loads(_required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native inventory case mismatch")
    sources = inventory.get("sources", {})
    if set(sources) < {"map", "history"}:
        raise ValueError("original Native map and history sources missing")
    for name in ("map", "history"):
        if sources[name].get("path") != name + ".json":
            raise ValueError("original Native source path mismatch")
    map_packet = load_sealed_json(_required(root, "map.json"), sources["map"]["sha256"])
    history = load_sealed_json(_required(root, "history.json"), sources["history"]["sha256"])
    role = case.removeprefix(config["assignment_id"] + "__")
    if role not in ("left_lane_u_turn", "outer_lane_u_turn"):
        raise ValueError("exact U-turn case suffix unknown")
    topology = verify_topology(map_packet, "left" if role == "left_lane_u_turn" else "outer")
    expected = 9 if (root / "fixture-provenance.json").is_file() else 900
    observed = verify_original_history(history, topology, case, expected_frames=expected)
    if inventory.get("frame_count") != expected or inventory.get("camera_views") != list(VIEWS):
        raise ValueError("source-profile four-view inventory incomplete")
    return observed


def measure_lane_use(attempt):
    measured = measure(attempt)
    return {key: measured[key] for key in ("requested_lane_id", "occupied_ring_lane_ids",
                                           "requested_lane_observed", "other_ring_lane_observed",
                                           "ring_frame_count")}


def measure_opposite_departure(attempt):
    measured = measure(attempt)
    return {key: measured[key] for key in ("opposite_departure_observed", "source_frame_count",
                                           "map_id", "actor_id")}


def analyze(attempt, output):
    root = Path(attempt)
    observed = measure(root)
    construction = json.loads(_required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in _required(root, "trace.jsonl").read_text().splitlines()]
    expected = 9 if (root / "fixture-provenance.json").is_file() else 900
    if len(trace) != expected:
        raise ValueError("original trace frame count incomplete")
    values = {"lane_use": measure_lane_use(root),
              "opposite_departure": measure_opposite_departure(root)}
    hashes = {name: _sha(_required(root, name)) for name in ("map.json", "history.json")}
    report = {"format": "worker-analysis-report", "case_id": observed["case_id"],
              "measurements": {"lane_use": {"method": "measure_lane_use", "value": values["lane_use"],
                                             "sources": hashes},
                               "opposite_departure": {"method": "measure_opposite_departure",
                                                      "value": values["opposite_departure"],
                                                      "sources": hashes}},
              "diagnostic_fixture": (root / "fixture-provenance.json").is_file(),
              "legal_verdict_claimed": False,
              "limitations": ["Measured ring-lane occupation and departure are not a legal verdict.",
                              "CPU fixtures do not establish physical Native success."]}
    recording = construction["recording_description"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    channel_values = {
        "original_roundabout_topology": {"source_sha256": hashes["map.json"], "map_id": observed["map_id"]},
        "original_operator_intention": {"source_sha256": hashes["history.json"], "intended_departure": "opposite_direction"},
        "original_ring_lane_history": {"source_sha256": hashes["history.json"], "occupied_ring_lane_ids": observed["occupied_ring_lane_ids"]},
        "original_departure_heading": {"source_sha256": hashes["history.json"], "opposite_departure_observed": observed["opposite_departure_observed"]},
        "original_four_camera_pixels": {"source_sha256": _sha(_required(root, "video_frames.jsonl")), "view_count": 4}}
    for channel in recording["channels"]:
        name = channel["name"]
        if name not in channel_values:
            raise ValueError("unexpected exact source channel: " + name)
        path = channels / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                               "value": channel_values[name]}) + "\n" for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context = channels / "reviewed_roundabout_map.json"
    context.write_text(json.dumps({"map_sha256": hashes["map.json"],
                                   "legal_judgment": "unresolved"}) + "\n")
    evidence.append({"name": "reviewed_roundabout_map", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": observed["case_id"], "measured_values": values,
              "target_checks": [{"target": "source-bound U-turn lane and departure",
                                 "requested": "left-lane use measured without legal cutoff",
                                 "measured": values, "method": "measure_lane_use/measure_opposite_departure",
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
