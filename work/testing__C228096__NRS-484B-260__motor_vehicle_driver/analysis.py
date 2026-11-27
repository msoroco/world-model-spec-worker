"""Saved-only private-way measurements from original, source-sealed evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from private_way_motion import measure
from private_way_site import load_site, REQUIRED_SOURCES


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(root, name):
    root = Path(root)
    path = root / name
    if not path.is_file() or path.is_symlink():
        relative = ("original-attempt/" + name if root.name == "original-attempt" else name)
        raise ValueError("Missing required source: " + relative)
    return path


def measure_original_private_way(attempt):
    """Return a source-bound report; never infer a legal right-of-way verdict."""
    attempt = Path(attempt).resolve()
    config = json.loads(_require(attempt, "config.json").read_text())
    case_id = config["selected_case_id"]
    original = attempt / "original-attempt"
    names = ["motion.jsonl", "motion-seal.json", "frame-map.json", "site.json",
             "actors.json", "inventory.json"]
    paths = {name: _require(original, name) for name in names}
    for name in REQUIRED_SOURCES:
        relative = "site-sources/" + name + ".source"
        paths[relative] = _require(original, relative)
    source_hashes = {"original-attempt/" + name: _sha(path)
                     for name, path in paths.items()}
    site = load_site(paths["site.json"], case_id)
    frame_map = json.loads(paths["frame-map.json"].read_text())
    actors = json.loads(paths["actors.json"].read_text())
    inventory = json.loads(paths["inventory.json"].read_text())
    if frame_map.get("case_id") != case_id or inventory.get("case_id") != case_id or \
            inventory.get("motion_sha256") != _sha(paths["motion.jsonl"]) or \
            inventory.get("frame_map_sha256") != _sha(paths["frame-map.json"]):
        raise ValueError("original private-way acquisition source join differs")
    measured = measure(original, case_id)
    if len(frame_map.get("frames", [])) != measured["frame_count"]:
        raise ValueError("original private-way frame map incomplete")
    if actors.get("highway_vehicles", {}) != measured["highway_actor_ids"]:
        raise ValueError("original private-way actor inventory differs")
    provenance = "synthetic_fixture" if measured["diagnostic_fixture"] else "native"
    if not measured["diagnostic_fixture"]:
        seal = json.loads(_require(attempt, "capture-seal.json").read_text())
        if seal.get("provenance_kind") != "native" or seal.get("frames") != 900:
            raise ValueError("sealed original Native private-way attempt required")
    context = {"reviewed_assertions": site["reviewed_assertions"],
               "connection_xy_m": site["connection_xy"],
               "highway_approach_sides": sorted(measured["highway_actor_ids"]),
               "source_hashes": source_hashes}
    common = ["original-attempt/motion.jsonl", "original-attempt/motion-seal.json",
              "original-attempt/frame-map.json"]
    site_sources = ["original-attempt/site.json"] + [
        "original-attempt/site-sources/" + name + ".source" for name in REQUIRED_SOURCES]
    requirement_sources = {0: common + site_sources, 1: common + site_sources,
                           2: common + ["original-attempt/actors.json"],
                           3: common + site_sources}
    measurements = {}
    for index, value in ((0, {"first_highway_frame": measured["first_highway_frame"],
                              "ego_stop_frames": measured["ego_stop_frames"]}),
                         (1, {"first_highway_frame": measured["first_highway_frame"],
                              "ego_highway_frames": measured["ego_highway_frames"]}),
                         (2, {"highway_actor_ids": measured["highway_actor_ids"],
                              "approach_first_last_distance_m":
                                  measured["approach_first_last_distance_m"],
                              "legal_yield_judgment": None}),
                         (3, context)):
        measurements["private_way_requirement_" + str(index)] = {
            "value": value,
            "method": "measure_original_private_way",
            "sources": {name: source_hashes[name] for name in requirement_sources[index]},
        }
    return {"format": "worker-analysis-report", "analysis_complete": True,
            "case_id": case_id, "measurements": measurements,
            "provenance_kind": provenance,
            "diagnostic_fixture": measured["diagnostic_fixture"],
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False,
            "limitations": ["Original private-way, highway and permitted-use facts require independent review.",
                            "Observed highway approach and ego progression do not decide legal yielding."]}


def save_result(attempt, report):
    from worker_exchange.native_output import validate_result

    attempt = Path(attempt).resolve()
    config = json.loads(_require(attempt, "config.json").read_text())
    case_id = config["selected_case_id"]
    original = attempt / "original-attempt"
    rows = [json.loads(line) for line in _require(original, "motion.jsonl").read_text().splitlines()]
    frames = [json.loads(line) for line in _require(attempt, "video_frames.jsonl").read_text().splitlines()]
    if len(rows) != len(frames) or any(
        frame.get("video_frame") != index or frame.get("carla_frame") != row.get("native_frame")
        or frame.get("time_s") != row.get("time_s")
        for index, (row, frame) in enumerate(zip(rows, frames))
    ):
        raise ValueError("saved private-way motion/video frame join differs")
    site = json.loads(_require(original, "site.json").read_text())
    channel_values = {
        "private_way_ownership_and_access": site["reviewed_assertions"],
        "public_highway_status_and_boundary": {
            "highway_polygon": site["highway_polygon"],
            "boundary_source_sha256": site["sources"]["boundary_map"]["sha256"]},
        "entry_or_crossing_connection": {
            "connection_xy": site["connection_xy"], "maneuver": config["maneuver"]},
        "all_highway_vehicle_approaches": None,
        "ego_precedence_motion": None,
        "four_camera_original_pixels": {
            "camera_archives": json.loads(_require(original, "inventory.json").read_text())
                               ["camera_archives"]},
    }
    description = config["case"]["recording_description"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        target = channels / (name + ".jsonl")
        with target.open("x") as stream:
            for row, frame in zip(rows, frames):
                value = channel_values[name]
                if name == "all_highway_vehicle_approaches":
                    value = row["highway_vehicles"]
                elif name == "ego_precedence_motion":
                    value = {"ego_on_highway": row["ego_on_highway"],
                             "ego_speed_mps": row["ego_speed_mps"]}
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(attempt))})
    context = channels / "reviewed_private_way_site_packet.json"
    context.write_text(json.dumps({"reviewed_private_way_site_packet": {
        "site_sha256": _sha(original / "site.json"),
        "review_status": "pending independent original review"}}) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    measured = report["measurements"]
    joined_sources = measured["private_way_requirement_3"]["sources"]
    first_frame = measured["private_way_requirement_0"]["value"]["first_highway_frame"]
    matched = type(first_frame) is int and first_frame >= 0
    def check(status, method):
        return {"status": status, "method": method, "sources": joined_sources,
                "details": {"diagnostic_fixture": report["diagnostic_fixture"]},
                "missing_evidence": [], "legal_verdict_claimed": False,
                "physical_causation_claimed": False}
    result = {
        "case_id": case_id,
        "measured_values": {name: item["value"] for name, item in measured.items()},
        "target_checks": [{"target": "ego reaches reviewed highway connection",
                           "requested": True, "measured": matched,
                           "method": "measure_original_private_way", "tolerance": 0,
                           "matched": matched, "physical_cause_confirmed": False,
                           "cause_evidence": joined_sources}],
        "setup_confirmed": True, "behavior_attempted": True,
        "maneuver_completed": matched,
        "termination_reason": "Saved original private-way observations; legal yielding pending independent review",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {
            "first_highway_frame": {"value": first_frame, "unit": "frame",
                                    "method": "source-sealed original ego progression",
                                    "time_window": "45-second original episode",
                                    "statistic": "first observed highway frame",
                                    "reference": "original-attempt/motion.jsonl"}},
        "physical_checks": {"setup": check("met", "reviewed source and actor join"),
                            "target": check("met" if matched else "not_met", "saved ego progression"),
                            "maneuver": check("met" if matched else "not_met", "saved ego progression")},
        "provenance_kind": report["provenance_kind"],
        "diagnostic_fixture": report["diagnostic_fixture"],
        "physical_acceptance_claimed": False,
    }
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior saved private-way analysis")
    report = measure_original_private_way(args.attempt)
    result = save_result(args.attempt, report)
    result_path = args.attempt / "result.json"
    if result_path.exists():
        raise ValueError("retain prior saved private-way result")
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
