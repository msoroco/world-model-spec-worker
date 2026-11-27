"""Saved-only original railway source measurements; no causal/legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import railway_7a as law
from native_capture import VIEWS

AID = "testing__C410753__NRS-484B-560-7a__heavy_vehicle_driver"


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
        raise ValueError("exact railway construction differs")
    name = case_id.removeprefix(AID + "__")
    if name not in law.CASE_AXES:
        raise ValueError("unselected railway case")
    inventory = json.loads(required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native railway inventory case differs")
    refs = inventory.get("sources", {})
    for key, filename in (("site", "site.json"), ("history", "history.json"),
                          ("frame_map", "frame-map.json")):
        if refs.get(key, {}).get("path") != filename or refs[key].get("sha256") != sha(required(root, filename)):
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
    for index, (row, mapping) in enumerate(zip(rows, frame_map)):
        if mapping != {"frame_index": index, "native_frame": row.get("source_frame"),
                       "time_s": row.get("time_s")}:
            raise ValueError("original railway frame-map join differs")
    if site.get("_packet_sha256") != inventory.get("reviewed_site_sha256"):
        raise ValueError("original railway source packet binding differs")
    return case_id, law.measure_frames(site, rows), rows, site, fixture


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
                raise ValueError("original railway trace and history differ")
    hashes = {name: sha(required(root, name)) for name in
              ("site.json", "history.json", "frame-map.json", "video_frames.jsonl")}
    values = {"maximum_trailing_end_ft": measured["maximum_trailing_end_ft"],
              "halt_before_15ft_observed": measured["halt_before_15ft_observed"],
              "space_evidence": measured["space_evidence"],
              "contact_evidence": measured["contact_evidence"],
              "causal_attribution": measured["causal_attribution"],
              "original_frame_count": len(frames), "legal_judgment": None}
    sources = {name: hashes[name] for name in ("site.json", "history.json", "frame-map.json")}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"railway_7a_requirement_" + str(i): {
                  "method": "measure", "value": values, "sources": sources}
                  for i in range(4)},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Source-observed contact and space do not establish halt causality.",
                              "Nearest-rail meaning and physical completion require independent review.",
                              "CPU fixtures do not establish Native physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    observations = {
        "rail_geometry": {"source_sha256": hashes["site.json"], "rails": site["track"]["rails"]},
        "vehicle_body_vertices": {"source_sha256": hashes["history.json"], "vehicle": site["vehicle"]["blueprint_id"]},
        "coupled_unit_geometry": {"source_sha256": hashes["history.json"], "units": len(site["vehicle"]["coupled_units"])},
        "source_frame_time": {"source_sha256": hashes["frame-map.json"], "frame_count": len(frames)},
        "trailing_end_distance_ft": {"source_sha256": hashes["history.json"], "maximum_ft": values["maximum_trailing_end_ft"]},
        "actual_speed_mps": {"source_sha256": hashes["history.json"], "halt": values["halt_before_15ft_observed"]},
        "downstream_body_gap_m": {"source_sha256": hashes["history.json"], "space_evidence": values["space_evidence"]},
        "undercarriage_contact": {"source_sha256": hashes["history.json"], "contact_evidence": values["contact_evidence"]},
        "control_history": {"source_sha256": hashes["history.json"], "causal_attribution": values["causal_attribution"]},
        "traffic_conflict_history": {"source_sha256": hashes["history.json"], "causal_attribution": values["causal_attribution"]},
        "four_view_frame_join": {"source_sha256": hashes["video_frames.jsonl"], "view_count": 4}}
    evidence = []
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in observations:
            raise ValueError("unexpected railway channel: " + name)
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
                                               "value": observations[name]}) + "\n"
                                  for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channels / "reviewed_railway_site.json"
    context.write_text(json.dumps({"reviewed_railway_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_railway_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": "source-bound heavy-vehicle railway crossing",
                                 "requested": construction["case_id"], "measured": values,
                                 "method": "railway_7a.measure_frames", "tolerance": 0,
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
