"""Saved-only near-side crosswalk front/cessation measurement; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import near_crosswalk as near
from native_capture import ASSIGNMENT, VIEWS


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
    if construction["case_id"] != case_id or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("selected near-side crosswalk construction differs")
    case_name = case_id.removeprefix(ASSIGNMENT + "__")
    case = next((item for item in near.CASES if item.name == case_name), None)
    if case is None:
        raise ValueError("unknown exact near-side crosswalk case")
    inventory = json.loads(required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native crosswalk inventory case mismatch")
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
        raise ValueError("original near-side crosswalk frame count incomplete")
    if inventory.get("camera_views") != list(VIEWS):
        raise ValueError("four-view Native inventory incomplete")
    for index, (row, mapping) in enumerate(zip(frames, frame_map)):
        if mapping != {"frame_index": index, "native_frame": row.get("original_frame"),
                       "time_s": row.get("time_s")}:
            raise ValueError("original frame-map join mismatch")
    measured = near.measure_original(frames, site, case, diagnostic_fixture=fixture)
    return case_id, measured, frames, site, fixture


def analyze(attempt, output):
    root = Path(attempt)
    case_id, measured, frames, site, fixture = measure(root)
    construction = json.loads(required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != len(frames):
        raise ValueError("original crosswalk trace count incomplete")
    if not fixture:
        for row, original in zip(trace, frames):
            if row.get("frame") != original["original_frame"] or \
                    abs(row.get("time_s", -1000) - original["time_s"]) > .005:
                raise ValueError("original crosswalk trace and source history differ")
    hashes = {name: sha(required(root, name)) for name in
              ("site.json", "history.json", "frame-map.json")}
    values = {"crosswalk_entry_frame": measured["crosswalk_entry_frame"],
              "stopped_before_entry": measured["stopped_before_entry"],
              "crosswalk_marked": site["marked"],
              "original_frame_count": len(frames), "legal_judgment": None}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"near_crosswalk_approach": {
                  "method": "measure", "value": values, "sources": hashes}},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["A physical cessation sample is a measured probe, not a minimum legal stop duration.",
                              "CPU fixtures do not establish original Native physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    observations = {
        "original_front_position": {"source_sha256": hashes["history.json"],
                                    "entry_frame": measured["crosswalk_entry_frame"]},
        "physical_cessation": {"source_sha256": hashes["history.json"],
                               "stopped_before_entry": measured["stopped_before_entry"]},
        "governing_stop_sign": {"source_sha256": hashes["site.json"],
                                "sign_id": site["stop_sign_id"]},
        "near_side_crosswalk_boundary": {"source_sha256": hashes["site.json"],
                                          "rect_m": site["near_crosswalk_rect_m"],
                                          "marked": site["marked"]},
        "original_four_camera_pixels": {"source_sha256": sha(required(root, "video_frames.jsonl")),
                                        "view_count": 4}}
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in observations:
            raise ValueError("unexpected crosswalk channel: " + name)
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
                                               "value": observations[name]}) + "\n"
                                  for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channels / "reviewed_crosswalk_site.json"
    context.write_text(json.dumps({"reviewed_crosswalk_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_crosswalk_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound vehicle front and pre-entry cessation",
                                 "requested": construction["case_id"], "measured": values,
                                 "method": "near_crosswalk.measure_original", "tolerance": 0,
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
