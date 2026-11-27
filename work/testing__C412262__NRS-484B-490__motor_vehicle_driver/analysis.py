"""Saved original highway/device/parking measurement without legal verdicts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from highway_observations import inside, point
from saved_finalizer import finalize
from highway_scene_construction import ASSIGNMENT, load_case

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    construction = json.loads(required(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    case = load_case(case_id)
    if construction["case_id"] != case_id or case_id not in config["supported_case_ids"]:
        raise ValueError("selected one-way parking construction differs")
    context = required(root, "context.json")
    original = required(root, "original-trace.jsonl")
    receipt = required(root, "receipt.json")
    cameras = required(root, "cameras.json")
    fixture = (root / "fixture-provenance.json").is_file()
    if fixture:
        provenance = json.loads(required(root, "fixture-provenance.json").read_text())
        if provenance.get("diagnostic_fixture") is not True:
            raise ValueError("synthetic fixture provenance mismatch")
        seal = json.loads(receipt.read_text())
        if (seal.get("source_kind") != "synthetic_diagnostic_fixture" or
                seal.get("case_id") != case_id or seal.get("assignment_id") != ASSIGNMENT or
                seal.get("context_sha256") != sha(context) or
                seal.get("trace_sha256") != sha(original) or
                seal.get("camera_manifest_sha256") != sha(cameras)):
            raise ValueError("synthetic fixture source seal mismatch")
        content = json.loads(context.read_text())
        rows = [json.loads(line) for line in original.read_text().splitlines()]
        if len(rows) != 9 or content.get("case_id") != case_id:
            raise ValueError("bounded diagnostic side trace incomplete")
        for key in ("highway_width_request", "device_request",
                    "activity_request", "parking_location_request"):
            if content.get(key) != case[key]:
                raise ValueError("diagnostic intervention differs from exact case: " + key)
        highway = content["highway_boundary_xy_m"]
        extent = content["device_extent_xy_m"]
        samples = []
        for index, row in enumerate(rows):
            if row.get("frame") != index or abs(row.get("time_s", -100) - index / 20) > .002:
                raise ValueError("bounded diagnostic highway cadence mismatch")
            body = [point(vertex) for vertex in row["vehicle_body_polygon_xy_m"]]
            samples.append({"frame": index,
                            "body_on_highway": all(inside(vertex, highway) for vertex in body),
                            "body_in_device_extent": all(inside(vertex, extent) for vertex in body),
                            "speed_mps": row["speed_mps"]})
        measurement = {"samples": samples, "narrow_highway_judgment": "unresolved",
                       "official_device_judgment": "unresolved", "parking_judgment": "unresolved",
                       "physical_acceptance": "unverified"}
    else:
        measurement = finalize(case_id, context, original, receipt, cameras)
    frame_count = 9 if fixture else 900
    values = {"original_frame_count": frame_count,
              "first_body_on_highway": measurement["samples"][0]["body_on_highway"],
              "last_body_on_highway": measurement["samples"][-1]["body_on_highway"],
              "first_body_in_device_extent": measurement["samples"][0]["body_in_device_extent"],
              "last_body_in_device_extent": measurement["samples"][-1]["body_in_device_extent"],
              "full_highway_width_profile_m": json.loads(context.read_text()).get("full_highway_width_profile_m"),
              "highway_status_source_label": json.loads(context.read_text()).get("highway_status"),
              "device_status_source_label": json.loads(context.read_text()).get("device_status"),
              "narrow_highway_judgment": "unresolved",
              "parking_judgment": "unresolved",
              "official_device_judgment": "unresolved"}
    hashes = {name: sha(required(root, name)) for name in
              ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")}
    return case, values, hashes, fixture, construction


def analyze(attempt, output):
    root = Path(attempt)
    case, values, hashes, fixture, construction = measure(root)
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != values["original_frame_count"]:
        raise ValueError("original Core trace and side history count differ")
    report = {"format": "worker-analysis-report", "case_id": case["case_id"],
              "measurements": {"narrow_highway_device_and_parking": {
                  "method": "measure", "value": values, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Width profile does not establish the statutory narrow-highway judgment.",
                              "Device pixels do not establish official authority or conformity.",
                              "Halt speed does not establish parking purpose.",
                              "A CPU diagnostic fixture does not establish original physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    descriptions = construction["recording_description"]["channels"]
    for channel in descriptions:
        name = channel["name"]
        target = channels / (name + ".jsonl")
        source_hash = hashes["cameras.json"] if name == "original_four_camera_pixels" else hashes["original-trace.jsonl"]
        with target.open("x") as stream:
            for row in trace:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": {"source_sha256": source_hash,
                                                   "case_id": case["case_id"],
                                                   "measurement": values}}, sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context_target = channels / "reviewed_original_highway_survey.json"
    context_target.write_text(json.dumps({"reviewed_original_highway_survey": {
        "source_sha256": hashes["context.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_original_highway_survey", "unit": "source",
                     "reference": str(context_target.relative_to(root))})
    result = {"case_id": case["case_id"], "measured_values": values,
              "target_checks": [{"target": "source-bound highway boundary, width, device and parking activity",
                                 "requested": case["variant"], "measured": values,
                                 "method": "highway_observations.observe",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Original highway, device and purpose review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
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
