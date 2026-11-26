"""Saved-only original signal, stop-reference and priority measurement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import native_signal as signal


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
    if construction["case_id"] != case_id or not case_id.startswith(signal.ASSIGNMENT + "__"):
        raise ValueError("exact inoperative-signal construction differs")
    case = next((item for item in signal.CASES
                 if case_id == signal.ASSIGNMENT + "__" + item.name), None)
    if case is None:
        raise ValueError("unknown exact inoperative-signal case")
    inventory = json.loads(required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or \
            inventory.get("source_kind") != "original_native" or \
            inventory.get("camera_views") != list(signal.VIEWS):
        raise ValueError("original Native signal inventory mismatch")
    names = (("site", "site.json"), ("ego_history", "ego-history.json"),
             ("other_history", "other-history.json"),
             ("frame_map", "frame-map.json"))
    for name, filename in names:
        ref = inventory.get("sources", {}).get(name, {})
        if ref.get("path") != filename or ref.get("sha256") != sha(required(root, filename)):
            raise ValueError("original signal source hash mismatch: " + filename)
    site_path = required(root, "site.json")
    site = json.loads(site_path.read_text())
    ego = json.loads(required(root, "ego-history.json").read_text())
    other = json.loads(required(root, "other-history.json").read_text())
    frame_map = json.loads(required(root, "frame-map.json").read_text())
    diagnostic = (root / "fixture-provenance.json").is_file()
    expected = 9 if diagnostic else signal.FULL_FRAMES
    if inventory.get("frame_count") != expected or \
            len(ego) != expected or len(other) != expected or len(frame_map) != expected:
        raise ValueError("original Native signal histories incomplete")
    for index, (erow, orow, mapping) in enumerate(zip(ego, other, frame_map)):
        if mapping != {"frame_index": index,
                       "native_frame": erow.get("original_frame"),
                       "time_s": erow.get("time_s")} or \
                orow.get("original_frame") != erow.get("original_frame"):
            raise ValueError("original two-vehicle frame-map join mismatch")
    measured = signal.measure_original(site, site_path, case, ego, other,
                                       diagnostic=diagnostic)
    return case_id, measured, site, ego, other, diagnostic


def analyze(attempt, output):
    root = Path(attempt)
    case_id, measured, site, ego, other, diagnostic = measure(root)
    construction = json.loads(required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in
             required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != len(ego):
        raise ValueError("original signal trace count incomplete")
    if not diagnostic:
        for row, original in zip(trace, ego):
            if row.get("frame") != original["original_frame"] or \
                    abs(row.get("time_s", -1000) - original["time_s"]) > .005:
                raise ValueError("original signal trace/source history differ")
    hashes = {name: sha(required(root, name)) for name in
              ("site.json", "ego-history.json", "other-history.json",
               "frame-map.json")}
    values = {**measured, "original_frame_count": len(ego),
              "signal_id": site["signal_id"], "legal_judgment": None}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {
                  "signal_at_entry": {"method": "measure", "value": {
                      "signal_id": site["signal_id"],
                      "entry_original_frame": measured["entry_original_frame"],
                      "installed_uncovered_inoperative": True}, "sources": hashes},
                  "stop_reference_and_cessation": {"method": "measure", "value": {
                      "reference": measured["stop_reference"],
                      "station_m": measured["reference_station_m"],
                      "stop_original_frame": measured["stop_original_frame"],
                      "position_ok": measured["stopped_at_required_position"]},
                      "sources": hashes},
                  "other_vehicle_priority": {"method": "measure", "value": {
                      "vehicle_id": site["other_vehicle_id"],
                      "priority_observed": measured["priority_vehicle_observed"]},
                      "sources": hashes},
                  "cautious_proceeding_context": {"method": "measure", "value": {
                      "through_highway_id": site["through_highway_id"],
                      "sightline_source_sha256": site["sightline_survey_source_sha256"],
                      "original_ego_speed_samples": [row["speed_mps"] for row in ego],
                      "legal_judgment": None},
                      "sources": hashes}},
              "diagnostic_fixture": diagnostic,
              "legal_verdict_claimed": False,
              "limitations": ["Cautious proceeding remains a source-grounded legal question.",
                              "CPU diagnostic fixtures do not establish original Native physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    observations = {
        "governing_signal_at_entry": {"signal_id": site["signal_id"],
                                      "entry_frame": measured["entry_original_frame"],
                                      "source_sha256": hashes["ego-history.json"]},
        "stop_reference_hierarchy": {"kind": measured["stop_reference"],
                                     "station_m": measured["reference_station_m"],
                                     "source_sha256": hashes["site.json"]},
        "ego_front_and_cessation": {"stop_frame": measured["stop_original_frame"],
                                    "position_ok": measured["stopped_at_required_position"],
                                    "source_sha256": hashes["ego-history.json"]},
        "other_vehicle_priority": {"priority_observed": measured["priority_vehicle_observed"],
                                   "source_sha256": hashes["other-history.json"]},
        "blind_sightline_and_through_highway": {
            "through_highway_id": site["through_highway_id"],
            "source_sha256": site["sightline_survey_source_sha256"]},
        "original_four_camera_pixels": {"views": list(signal.VIEWS),
                                        "source_sha256": sha(required(root, "video_frames.jsonl"))}}
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        if name not in observations:
            raise ValueError("unexpected signal channel: " + name)
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
                                               "value": observations[name]}) + "\n"
                                  for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channels / "reviewed_signal_site.json"
    context.write_text(json.dumps({"reviewed_signal_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_signal_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound original signal, cessation and vehicle priority",
                                 "requested": construction["case_id"],
                                 "measured": values, "method": "native_signal.measure_original",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in signal.VIEWS],
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
