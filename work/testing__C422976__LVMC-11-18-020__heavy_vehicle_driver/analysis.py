"""Saved-only School-Xing entry and person-state measurement, without a verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import school_crossing as school
from native_capture import VIEWS


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
    if construction["case_id"] != case_id or not case_id.startswith(school.ASSIGNMENT + "__"):
        raise ValueError("selected School-Xing construction differs")
    case_name = case_id.removeprefix(school.ASSIGNMENT + "__")
    case = next((c for c in school.CASES if c.name == case_name), None)
    if case is None:
        raise ValueError("unknown exact School-Xing case")
    inventory = json.loads(required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native School-Xing inventory case mismatch")
    sources = inventory.get("sources", {})
    for name, filename in (("site", "site.json"), ("history", "history.json"),
                           ("frame_map", "frame-map.json")):
        ref = sources.get(name, {})
        if ref.get("path") != filename or ref.get("sha256") != sha(required(root, filename)):
            raise ValueError("source hash mismatch: " + filename)
    site = json.loads(required(root, "site.json").read_text())
    frames = json.loads(required(root, "history.json").read_text())
    frame_map = json.loads(required(root, "frame-map.json").read_text())
    fixture = (root / "fixture-provenance.json").is_file()
    expected = 9 if fixture else 900
    if inventory.get("frame_count") != expected or len(frames) != expected or len(frame_map) != expected:
        raise ValueError("original School-Xing frame count incomplete")
    if inventory.get("camera_views") != list(VIEWS):
        raise ValueError("four-view Native inventory incomplete")
    for index, (row, mapping) in enumerate(zip(frames, frame_map)):
        if mapping != {"frame_index": index, "native_frame": row.get("original_frame"),
                       "time_s": row.get("time_s")}:
            raise ValueError("original frame-map join mismatch")
    measured = school.measure_original(frames, site, case)
    return case_id, measured, frames, site, fixture


def analyze(attempt, output):
    root = Path(attempt)
    case_id, measured, frames, site, fixture = measure(root)
    construction = json.loads(required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != len(frames):
        raise ValueError("original School-Xing trace count incomplete")
    if not fixture:
        for row, original in zip(trace, frames):
            if row.get("frame") != original["original_frame"] or \
                    abs(row.get("time_s", -1000) - original["time_s"]) > .005:
                raise ValueError("original trace and School-Xing source history differ")
    hashes = {name: sha(required(root, name)) for name in
              ("site.json", "history.json", "frame-map.json", "video_frames.jsonl")}
    entry = measured["entry"]
    values = {"crossing_entry_frame": entry["frame"] if entry else None,
              "person_in_crossing_at_entry": entry["person_in_crossing"] if entry else None,
              "person_attempt_observed_at_entry": entry["person_attempt_observed"] if entry else None,
              "person_side_relative_to_approach_at_entry":
                  entry["person_side_relative_to_approach"] if entry else None,
              "crossing_width_ft_measured": measured["crossing_width_ft_measured"],
              "sign_advance_distance_ft_measured": measured["sign_advance_distance_ft_measured"],
              "sign_displayed_at_entry": measured["sign_displayed_at_entry"],
              "original_frame_count": len(frames), "legal_judgment": None}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"school_crossing_entry": {
                  "method": "measure", "value": values, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["An observed attempt flag requires independent original-source review.",
                              "Approaching-side and approximately twelve feet remain unresolved legal phrases.",
                              "CPU fixtures do not establish original Native physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    observations = {
        "original_vehicle_front": {"source_sha256": hashes["history.json"],
                                   "entry_frame": values["crossing_entry_frame"]},
        "original_person_position": {"source_sha256": hashes["history.json"],
                                     "person_id": site["person"]["id"]},
        "attempt_evidence": {"source_sha256": site["source_records"]["pedestrian_source"]["sha256"],
                             "attempt_at_entry": values["person_attempt_observed_at_entry"]},
        "sign_display": {"source_sha256": hashes["site.json"],
                         "sign_id": site["sign_id"], "display_at_entry": values["sign_displayed_at_entry"]},
        "crossing_geometry": {"source_sha256": hashes["site.json"],
                              "rect_m": site["crossing_rect_m"],
                              "marking": site["crossing_marking"]},
        "municipal_context": {"source_sha256":
                              site["source_records"]["municipal_authority"]["sha256"],
                              "jurisdiction": site["jurisdiction"]},
        "vehicle_class_route": {"source_sha256":
                                site["source_records"]["vehicle_classification"]["sha256"],
                                "vehicle_class": site["vehicle_class"]},
        "four_view_video": {"source_sha256": hashes["video_frames.jsonl"],
                            "view_count": 4}}
    evidence = []
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in observations:
            raise ValueError("unexpected School-Xing channel: " + name)
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
                                              "value": observations[name]}) + "\n"
                                  for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channels / "reviewed_school_crossing_site.json"
    context.write_text(json.dumps({"reviewed_school_crossing_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_school_crossing_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound School-Xing crossing and person entry",
                                 "requested": construction["case_id"], "measured": values,
                                 "method": "school_crossing.measure_original", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Saved original review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
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
