"""Saved-only C125697 finalizer over sealed original actor and device history."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import median_source
from worker_exchange.native_output import physical_result, validate_result

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _source_manifest(root: Path) -> dict:
    retained = root / "source-manifest.json"
    if not retained.is_file():
        alias = _required(root, "original-source-manifest.json")
        if (root / "fixture-provenance.json").is_file():
            provenance = json.loads((root / "fixture-provenance.json").read_text())
            if provenance.get("diagnostic_fixture") is not True or provenance.get("physical_acceptance_claimed") is not False:
                raise ValueError("diagnostic source provenance differs")
        else:
            seal = json.loads(_required(root, "capture-seal.json").read_text())
            if (seal.get("provenance_kind") != "native" or
                    seal.get("sources", {}).get("original-source-manifest.json") != _sha(alias)):
                raise ValueError("Native original-source alias is unsealed")
        retained.write_bytes(alias.read_bytes())
    return json.loads(retained.read_text())


def measure_crossing_highways(scene: dict) -> dict:
    return {"crossing_id": scene["crossing"]["id"],
            "crossing_kind": scene["crossing"]["kind"],
            "ego_highway": scene["ego_highway"],
            "other_highway": scene["other_highway"],
            "distinct_highways": scene["ego_highway"] != scene["other_highway"]}


def measure_entry_timing(measured: dict) -> dict:
    return {"ego_entry": measured["ego_entry"],
            "other_entry": measured["other_entry"],
            "intersection_entry_time_difference_s":
                measured["intersection_entry_time_difference_s"],
            "native_first_frame_id": measured["native_first_frame_id"]}


def measure_approach_side(measured: dict) -> dict:
    return {"ego_approach_side": measured["ego_approach_side"],
            "other_approach_side": measured["other_approach_side"],
            "road_ids": measured["road_ids"]}


def measure_yield_response(measured: dict) -> dict:
    return {"ego_entered_after_other_exit": measured["ego_entered_after_other_exit"],
            "other_exit": measured["other_exit"],
            "legal_yield_judgment": "unresolved"}


def measure_device_context(scene: dict, measured: dict) -> dict:
    return {"governing_signal": scene["governing_signal"],
            "signal_inoperative_all_frames": True,
            "subsection_4_applicability_review": scene.get("subsection_4_applicability_review"),
            "legal_applicability": "unresolved"}


def measure_opposing_turn_context(scene: dict) -> dict:
    return {"ego_route_xy_m": scene["ego_route_xy_m"],
            "other_route_xy_m": scene["other_route_xy_m"],
            "opposing_left_turn_excluded_source": scene.get("opposing_left_turn_excluded_source"),
            "legal_exclusion": "unresolved"}


def analyze(attempt: Path, output: Path) -> dict:
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    construction = json.loads(_required(root, "construction.json").read_text())
    case = config["selected_case_id"]
    if construction.get("case_id") != case or case not in {
            "testing__C125697__NRS-484B-250-2__motor_vehicle_driver__" + suffix
            for suffix in ("timing_below_training", "timing_inside_training",
                           "timing_above_training", "right_approach_inside")}:
        raise ValueError("wrong selected median-opening construction")
    scene = json.loads(_required(root, "scene.json").read_text())
    geometry = json.loads(_required(root, "crossing_geometry.json").read_text())
    box = scene["crossing"]["bounds_xy_m"]
    expected_polygon = [[box[0], box[1]], [box[2], box[1]],
                        [box[2], box[3]], [box[0], box[3]]]
    if (geometry.get("intersection_xy_m") != expected_polygon or
            geometry.get("source_opendrive_sha256") !=
            scene["crossing"]["opendrive_sha256"]):
        raise ValueError("original crossing geometry differs from reviewed site")
    manifest = _source_manifest(root)
    _required(root, manifest["sources"]["native_trace"]["path"])
    diagnostic = (root / "fixture-provenance.json").is_file()
    audited = median_source.audit_saved_sources(root, manifest, scene,
                                                 diagnostic_fixture=diagnostic)
    measured = audited["observations"]
    if measured["ego_approach_side"] != config["ego_approach_side"] or (
            config["requested_entry_offset_s"] != next(
                row["planned_entry_time_difference_s"] for row in
                json.loads(_required(root, "case-plan.json").read_text())["cases"]
                if row["case_id"] == case)):
        raise ValueError("selected timing or approach request changed")
    original = json.loads(_required(root, manifest["sources"]["native_trace"]["path"]).read_text())
    frames = original["frames"]
    mapping = [json.loads(line) for line in _required(root, "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in _required(root, "trace.jsonl").read_text().splitlines()]
    crossing_history = [json.loads(line) for line in _required(root, "crossing_history.jsonl").read_text().splitlines()]
    if len(mapping) != len(trace) or len(trace) != len(frames) or len(crossing_history) != len(frames):
        raise ValueError("original trace/frame-map count differs")
    for index, (row, frame, video, crossing) in enumerate(zip(trace, frames, mapping, crossing_history)):
        if (row.get("frame") != frame["native_frame_id"] or
                row.get("time_s") != frame["native_elapsed_seconds"] or
                video.get("video_frame") != index or
                video.get("carla_frame") != row["frame"] or
                video.get("time_s") != row["time_s"] or
                crossing.get("frame") != row["frame"] or
                crossing.get("time_s") != row["time_s"] or
                crossing.get("ego_vertices_m") != frame["ego"]["body_vertices_xy_m"]):
            raise ValueError("original trace/frame-map identity differs")
    description = construction["recording_description"]
    if description != next(c["recording_description"] for c in json.loads(
            _required(root, "case-plan.json").read_text())["cases"] if c["case_id"] == case):
        raise ValueError("selected recording description changed")
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=False)
    body_path = channel_dir / "intersection_body_history.jsonl"
    signal_path = channel_dir / "governing_signal_readback.jsonl"
    body_path.write_text("".join(json.dumps({
        "time_s": row["native_elapsed_seconds"],
        "value": {"ego": row["ego"], "other": row["other"]}}) + "\n"
        for row in frames))
    signal_path.write_text("".join(json.dumps({
        "time_s": row["native_elapsed_seconds"],
        "value": row["signal_readback"]}) + "\n" for row in frames))
    site_path = channel_dir / "reviewed_site_device_highway_packet.json"
    site_path.write_text(json.dumps({"reviewed_site_device_highway_packet": {
        "crossing": scene["crossing"], "ego_highway": scene["ego_highway"],
        "other_highway": scene["other_highway"], "source_sha256": audited["source_sha256"]}},
        indent=2) + "\n")
    approach_path = channel_dir / "approach_and_turn_intent.json"
    approach_path.write_text(json.dumps({"approach_and_turn_intent": {
        "ego_route_xy_m": scene["ego_route_xy_m"],
        "other_route_xy_m": scene["other_route_xy_m"],
        "opposing_left_turn_excluded_source": scene.get("opposing_left_turn_excluded_source"),
        "legal_judgment": "unresolved"}}, indent=2) + "\n")
    refs = {
        "intersection_body_history": body_path,
        "governing_signal_readback": signal_path,
        "reviewed_site_device_highway_packet": site_path,
        "approach_and_turn_intent": approach_path,
    }
    evidence = [{"name": item["name"], "unit": item["unit"],
                 "reference": str(refs[item["name"]].relative_to(root))}
                for item in description["channels"] + description["context_inputs"]]
    requested = config["requested_entry_offset_s"]
    observed = measured["intersection_entry_time_difference_s"]
    ranges = json.loads(_required(root, "judgment-probe-plan.json").read_text())["ranges"]
    if len(ranges) != 1 or ranges[0]["variable"] != "intersection_entry_time_difference":
        raise ValueError("frozen judgment coverage range missing")
    minimum, maximum = ranges[0]["source_minimum"], ranges[0]["source_maximum"]
    if case.endswith("__timing_below_training"):
        coverage_matched = observed < minimum
        coverage_band = "below_training_range"
    elif case.endswith("__timing_above_training"):
        coverage_matched = observed > maximum
        coverage_band = "above_training_range"
    else:
        coverage_matched = minimum <= observed <= maximum
        coverage_band = "inside_training_range"
    checks = [
        {"target": "both_original_entries_observed", "requested": True,
         "measured": True,
         "method": "original footprint entry transitions", "tolerance": 0,
         "matched": True,
         "physical_cause_confirmed": False,
         "cause_evidence": audited["source_sha256"]},
        {"target": "entry_time_difference_training_coverage", "requested": {
             "coverage_band": coverage_band, "requested_offset_s": requested,
             "source_minimum_s": minimum, "source_maximum_s": maximum},
         "measured": observed, "method": "original ego and other entry brackets; training bounds are not legal thresholds",
         "tolerance": 0, "matched": coverage_matched,
         "physical_cause_confirmed": False,
         "cause_evidence": audited["source_sha256"]},
        {"target": "mapped_ego_approach_side", "requested": config["ego_approach_side"],
         "measured": measured["ego_approach_side"],
         "method": "original reviewed route vectors joined to participant identity",
         "tolerance": 0, "matched": measured["ego_approach_side"] == config["ego_approach_side"],
         "physical_cause_confirmed": False,
         "cause_evidence": audited["source_sha256"]},
    ]
    result = {
        "case_id": case,
        "measured_values": measured, "target_checks": checks,
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": f"{len(frames)} source frames analyzed; physical and legal review pending",
        "physical_failure_flags": [],
        "trace_reference": "trace.jsonl",
        "video_references": [manifest["sources"]["camera_" + name]["path"] for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence,
        "realized_observables": {},
        "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False,
        "legal_judgment": "unresolved",
    }
    result = physical_result(root, result)
    validate_result(result)
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    measurement_specs = {
        "crossing_highways": ("measure_crossing_highways", measure_crossing_highways(scene),
                              ["scene.json", "opendrive.xodr", "highway_identity.json"]),
        "entry_timing": ("measure_entry_timing", measure_entry_timing(measured),
                        ["native_trace.json", "crossing_history.jsonl", "scene.json"]),
        "approach_side": ("measure_approach_side", measure_approach_side(measured),
                         ["native_trace.json", "crossing_history.jsonl", "scene.json"]),
        "yield_response": ("measure_yield_response", measure_yield_response(measured),
                           ["native_trace.json", "scene.json"]),
        "device_context": ("measure_device_context", measure_device_context(scene, measured),
                           ["native_trace.json", "scene.json", "device_inventory.json"]),
        "opposing_turn_context": ("measure_opposing_turn_context", measure_opposing_turn_context(scene),
                                  ["scene.json", "native_trace.json"]),
    }
    measurements = {key: {"method": method, "value": value,
                          "sources": {name: _sha(_required(root, name)) for name in inputs}}
                    for key, (method, value, inputs) in measurement_specs.items()}
    report = {
        "format": "worker-analysis-report", "case_id": case,
        "measurements": measurements,
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "diagnostic_fixture": diagnostic,
        "legal_verdict_claimed": False,
        "limitations": [
            "Original highway/device context and subsection 4 applicability need independent review.",
            "Diagnostic fixtures do not establish physical motion or camera visibility.",
        ],
    }
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({"case_id": analyze(args.attempt, args.output)["case_id"]}))


if __name__ == "__main__":
    main()
