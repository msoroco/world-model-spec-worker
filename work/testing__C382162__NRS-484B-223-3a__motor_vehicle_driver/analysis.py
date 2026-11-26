"""Saved-only original center-lane occupancy, route and intent finalizer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from center_lane_probe import measure_exact
from center_lane_site import verify_reviewed_site
from native_capture import ASSIGNMENT, KINDS, VIEWS


def required(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("required original source path escapes attempt")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + str(relative))
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text())
    construction = json.loads(required(root, "construction.json").read_text())
    case_id = config.get("selected_case_id")
    if (case_id != construction.get("case_id") or
            case_id not in {ASSIGNMENT + "__" + kind for kind in KINDS}):
        raise ValueError("selected center-lane construction case mismatch")
    inventory = json.loads(required(root, "native/inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native inventory identity mismatch")
    refs = inventory.get("sources", {})
    names = {"site": "native/site.json", "history": "native/history.json",
             "frame_map": "native/frame-map.json", "purpose": "pre-entry-intent.json"}
    for name, filename in names.items():
        ref = refs.get(name, {})
        if ref.get("path") != filename or ref.get("sha256") != sha(required(root, filename)):
            raise ValueError("original source hash mismatch: " + filename)
    site = json.loads(required(root, names["site"]).read_text())
    road = required(root, "road.xodr").read_text()
    verify_reviewed_site(root, site, case_id.removeprefix(ASSIGNMENT + "__"), road)
    purpose = json.loads(required(root, names["purpose"]).read_text())
    frames = json.loads(required(root, names["history"]).read_text())
    mapping = json.loads(required(root, names["frame_map"]).read_text())
    fixture = required(root, "fixture-provenance.json").is_file() if (root / "fixture-provenance.json").exists() else False
    expected = 9 if fixture else 900
    if inventory.get("frame_count") != expected or len(frames) != expected or len(mapping) != expected:
        raise ValueError("original 20 Hz center-lane history incomplete")
    if inventory.get("camera_views") != list(VIEWS):
        raise ValueError("four-view original Native inventory incomplete")
    for original, sources in zip(frames, mapping):
        if (sources.get("original_frame") != original["original_frame"] or
                abs(sources.get("time_s", -1000) - original["time_s"]) > .005 or
                set(sources.get("camera_sources", {})) != set(VIEWS)):
            raise ValueError("original camera/frame source join mismatch")
        for view in VIEWS:
            binding = sources["camera_sources"][view]
            if binding.get("sha256") != sha(required(root, binding.get("path", ""))):
                raise ValueError("original camera source bytes changed: " + view)
    if purpose.get("case_id") != case_id:
        raise ValueError("independent intent case mismatch")
    measured = measure_exact(site, case_id.removeprefix(ASSIGNMENT + "__"), frames, purpose)
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != expected or any(a.get("frame") != b["original_frame"] or
                                     abs(a.get("time_s", -1000) - b["time_s"]) > .005
                                     for a, b in zip(trace, frames)):
        raise ValueError("original route history and Native trace differ")
    return case_id, measured, frames, site, fixture, refs


def analyze(attempt, output):
    root = Path(attempt).resolve()
    case_id, measured, frames, site, fixture, refs = measure(root)
    construction = json.loads(required(root, "construction.json").read_text())
    source_paths = ("native/site.json", "pre-entry-intent.json",
                    "native/history.json", "native/frame-map.json", "road.xodr")
    measured_outputs = {
        "lane_design": {"center_lane_id": site["route"]["center_lane_id"],
                        "highway_road_id": site["highway_road_id"]},
        "native_occupancy": {"frames": measured["center_lane_occupancy_frames"]},
        "pre_entry_intent": {"declared_purpose": measured["declared_purpose"],
                             "source_ref": measured["purpose_source"]},
        "left_turn_directions": {"relationship": measured["route_relationship"],
                                 "left_turn_frames": measured["observed_left_turn_frames"]},
        "purpose_contrasts": {"purpose": measured["declared_purpose"],
                              "left_turn_frames": measured["observed_left_turn_frames"],
                              "right_turn_frames": measured["observed_right_turn_frames"]},
        "alley_junction_classification": {"junction_kind": measured["junction_kind"],
                                          "intersection_eligible": measured["intersection_eligible"]}}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {key: {"method": "measure", "value": value,
                                      "sources": {name: sha(required(root, name))
                                                  for name in source_paths}}
                               for key, value in measured_outputs.items()},
              "diagnostic_fixture": fixture, "legal_verdict_claimed": False,
              "limitations": ["Purpose sufficiency remains unresolved; no numeric lane-use cutoff is inferred.",
                              "CPU fixtures do not establish original Native physical success."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    context = {"reviewed_highway_design": refs["site"]["sha256"],
               "pre_entry_purpose": refs["purpose"]["sha256"],
               "original_lane_occupancy": refs["history"]["sha256"],
               "original_route_and_maneuver": refs["history"]["sha256"],
               "street_or_alley_junction": refs["site"]["sha256"],
               "original_four_camera_pixels": refs["frame_map"]["sha256"]}
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        if name not in context:
            raise ValueError("unexpected center-lane observation channel")
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"], "value": {
            "source_sha256": context[name], "measured": measured}}, sort_keys=True) + "\n"
                                  for row in frames))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context_path = channels / "reviewed_center_lane_site.json"
    context_path.write_text(json.dumps({"reviewed_center_lane_site": {
        "site_sha256": refs["site"]["sha256"],
        "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_center_lane_site", "unit": "source",
                     "reference": str(context_path.relative_to(root))})
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "source-bound original lane, route and pre-entry intent",
                                 "requested": case_id, "measured": measured,
                                 "method": "center_lane_probe.measure_exact", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": {name: ref["sha256"] for name, ref in refs.items()}}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
