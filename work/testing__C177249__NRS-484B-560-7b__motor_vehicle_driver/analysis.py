"""Saved-only railway instruction analysis from sealed original sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import railway_7b as law
from native_capture import VIEWS

AID = "testing__C177249__NRS-484B-560-7b__motor_vehicle_driver"
CHANNELS = (
    "rail_crossing_geometry", "device_identity_and_officiality", "device_indication_history",
    "governed_movement", "officer_identity_and_direction_history", "driver_identity",
    "original_body_entry_exit", "actual_speed_and_brake", "four_camera_frame_join",
)


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
    case_id = config.get("selected_case_id")
    if construction.get("case_id") != case_id or not case_id.startswith(AID + "__"):
        raise ValueError("exact instruction construction differs")
    name = case_id.removeprefix(AID + "__")
    if name not in law.CASES:
        raise ValueError("unselected railway instruction case")
    inventory = json.loads(required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native railway inventory differs")
    for key, filename in (("site", "site.json"), ("history", "history.json"),
                          ("frame_map", "frame-map.json")):
        entry = inventory.get("sources", {}).get(key, {})
        if entry.get("path") != filename or entry.get("sha256") != sha(required(root, filename)):
            raise ValueError("original railway source hash mismatch: " + filename)
    site = json.loads(required(root, "site.json").read_text())
    law.validate_site(site, name)
    rows = json.loads(required(root, "history.json").read_text())
    frame_map = json.loads(required(root, "frame-map.json").read_text())
    fixture = (root / "fixture-provenance.json").is_file()
    count = 9 if fixture else 900
    if inventory.get("frame_count") != count or len(rows) != count or len(frame_map) != count:
        raise ValueError("original railway frame count incomplete")
    if inventory.get("camera_views") != list(VIEWS):
        raise ValueError("four-view original railway inventory incomplete")
    if site.get("_packet_sha256") != inventory.get("reviewed_site_sha256"):
        raise ValueError("reviewed railway site binding differs")
    for index, (row, mapping) in enumerate(zip(rows, frame_map)):
        if mapping != {"frame_index": index, "native_frame": row.get("source_frame"),
                       "time_s": row.get("time_s")}:
            raise ValueError("original railway frame map differs")
    return case_id, law.measure(site, rows), rows, site, fixture


def analyze(attempt, output):
    root = Path(attempt)
    case_id, measured, frames, site, fixture = measure(root)
    construction = json.loads(required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != len(frames):
        raise ValueError("original railway trace count incomplete")
    if not fixture:
        for row, original in zip(trace, frames):
            if row.get("frame") != original["source_frame"] or abs(row.get("time_s", -1000) - original["time_s"]) > .005:
                raise ValueError("original railway trace/history differs")
    hashes = {name: sha(required(root, name)) for name in
              ("site.json", "history.json", "frame-map.json", "video_frames.jsonl")}
    values = {key: value for key, value in measured.items() if key != "samples"}
    values.update(original_frame_count=len(frames), legal_judgment=None)
    sources = {name: hashes[name] for name in ("site.json", "history.json", "frame-map.json")}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"railway_7b_requirement_" + str(index): {
                  "method": "measure", "value": values, "sources": sources}
                  for index in range(2)},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Officiality and officer authenticity require independent original source review.",
                              "Permissive clear does not create an affirmative duty to proceed.",
                              "CPU fixture cannot establish physical success."]}
    channel_root = root / "channels"
    channel_root.mkdir(exist_ok=False)
    observations = {
        "rail_crossing_geometry": {"source_sha256": hashes["site.json"], "crossing": site["crossing"]},
        "device_identity_and_officiality": {"source_sha256": hashes["site.json"], "device": site["device"]},
        "device_indication_history": {"source_sha256": hashes["history.json"], "indication": frames[0]["device_indication"]},
        "governed_movement": {"source_sha256": hashes["site.json"], "ref": site["device"]["governed_movement_ref"]},
        "officer_identity_and_direction_history": {"source_sha256": hashes["history.json"],
                                                   "officer": site.get("officer"), "direction": frames[0]["officer_direction"]},
        "driver_identity": {"source_sha256": hashes["site.json"], "vehicle": site["vehicle"]},
        "original_body_entry_exit": {"source_sha256": hashes["history.json"],
                                      "crossed": values["observed_crossing_entry"],
                                      "full_exit": values["observed_full_exit"]},
        "actual_speed_and_brake": {"source_sha256": hashes["history.json"],
                                   "halt_before": values["observed_halt_before_entry"]},
        "four_camera_frame_join": {"source_sha256": hashes["video_frames.jsonl"], "view_count": 4},
    }
    evidence = []
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in CHANNELS:
            raise ValueError("unexpected railway instruction channel: " + name)
        target = channel_root / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
                                               "value": observations[name]}) + "\n" for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channel_root / "reviewed_railway_site.json"
    context.write_text(json.dumps({"reviewed_railway_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_railway_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound crossing instruction and vehicle response",
                                 "requested": case_id, "measured": values,
                                 "method": "railway_7b.measure", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Original source review pending",
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
