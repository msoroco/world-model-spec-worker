"""Saved original side geometry measurement; statutory judgment remains unresolved."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_side_observations import polyline, point, signed_offset
from saved_finalizer import finalize
from street_scene_construction import ASSIGNMENT, load_case

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
        for key in ("street_direction_request", "vehicle_side_request",
                    "activity_request", "notice_request"):
            if content.get(key) != case[key]:
                raise ValueError("diagnostic intervention differs from exact case: " + key)
        route = polyline(content["permitted_direction_centerline_xy_m"])
        samples = []
        for index, row in enumerate(rows):
            if row.get("frame") != index or abs(row.get("time_s", -100) - index / 20) > .002:
                raise ValueError("bounded diagnostic side cadence mismatch")
            body = [point(vertex) for vertex in row["vehicle_body_polygon_xy_m"]]
            offsets = [signed_offset(vertex, route)["signed_left_offset_m"] for vertex in body]
            samples.append({"frame": index, "body_signed_left_offset_range_m":
                            [min(offsets), max(offsets)]})
        measurement = {"samples": samples, "left_hand_side_judgment": "unresolved",
                       "stand_or_park_judgment": "unresolved",
                       "notice_legal_applicability_judgment": "unresolved",
                       "physical_acceptance": "unverified"}
    else:
        measurement = finalize(case_id, context, original, receipt, cameras)
    frame_count = 9 if fixture else 900
    values = {"original_frame_count": frame_count,
              "first_body_signed_left_offset_range_m":
                  measurement["samples"][0]["body_signed_left_offset_range_m"],
              "last_body_signed_left_offset_range_m":
                  measurement["samples"][-1]["body_signed_left_offset_range_m"],
              "one_way_status_source_label": json.loads(context.read_text()).get("one_way_status"),
              "notice_state_source_label": json.loads(context.read_text()).get("notice_state"),
              "statutory_side_judgment": "unresolved",
              "stand_or_park_judgment": "unresolved",
              "official_notice_applicability_judgment": "unresolved"}
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
              "measurements": {"one_way_left_side_geometry": {
                  "method": "measure", "value": values, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Signed offsets do not establish the legal left-hand side.",
                              "Halt speed does not establish standing or parking purpose.",
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
    context_target = channels / "reviewed_original_street_survey.json"
    context_target.write_text(json.dumps({"reviewed_original_street_survey": {
        "source_sha256": hashes["context.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_original_street_survey", "unit": "source",
                     "reference": str(context_target.relative_to(root))})
    result = {"case_id": case["case_id"], "measured_values": values,
              "target_checks": [{"target": "source-bound one-way side geometry",
                                 "requested": case["variant"], "measured": values,
                                 "method": "one_way_side_observations.signed_offset",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Original side and purpose review pending",
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
