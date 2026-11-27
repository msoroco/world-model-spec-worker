"""Saved-only, source-bound residential driveway measurement and projection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from driveway_measurement import load_sources, measure


def _read(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + str(path))
    return json.loads(path.read_text())


def _rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_context(values, geometry):
    return {"district": geometry["district"], "access": geometry["access"],
            "connected_roadway": geometry["road_connection"],
            "district_source": geometry["district_source"],
            "frontage_source": geometry["frontage_source"],
            "driveway_source": geometry["private_driveway_source"]}


def measure_sidewalk_stop(values, geometry):
    return {"first_sidewalk_frame": values["first_sidewalk_frame"],
            "last_pre_sidewalk_halt_frame": values["last_pre_sidewalk_halt_frame"],
            "pre_sidewalk_speed_mps": values["pre_sidewalk_speed_mps"],
            "statutory_immediately_prior_judgment": None}


def measure_pedestrian(values, geometry):
    return {"source_present": values["pedestrian_source_present"],
            "minimum_center_separation_m": values["minimum_pedestrian_center_separation_m"],
            "collision_avoidance_necessity_judgment": None}


def measure_roadway(values, geometry):
    return {"source_present": values["roadway_vehicle_source_present"],
            "first_roadway_frame": values["first_roadway_frame"],
            "minimum_center_separation_m": values["minimum_roadway_vehicle_center_separation_m"],
            "right_of_way_judgment": None}


def build(attempt):
    attempt = Path(attempt).resolve()
    config = _read(attempt / "config.json")
    case = config["case"]
    original = attempt / "original-attempt"
    for name in ("inventory.json", "frame_map.json", "driveway_geometry.json", "activity.json"):
        if not (original / name).is_file():
            raise ValueError("Missing required source: original-attempt/" + name)
    marker = attempt / "fixture-provenance.json"
    diagnostic = marker.is_file()
    if diagnostic:
        provenance = _read(marker)
        if (provenance.get("diagnostic_fixture") is not True or
                provenance.get("physical_acceptance_claimed") is not False):
            raise ValueError("untrusted synthetic driveway provenance")
    inventory, sources = load_sources(original, diagnostic=diagnostic)
    values = measure(original, case, diagnostic=diagnostic)
    frames = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    original_frames = sources["frame_map"]["frames"]
    if (len(frames) != len(trace) or len(frames) != len(original_frames) or
            any(frames[i].get("video_frame") != i or
                frames[i].get("carla_frame") != row["frame"] or
                frames[i].get("time_s") != row["time_s"] or
                trace[i].get("frame") != row["frame"]
                for i, row in enumerate(original_frames))):
        raise ValueError("original driveway trace/video/frame join differs")
    geometry = sources["driveway_geometry"]
    paths = ("original-attempt/driveway_geometry.json", "original-attempt/activity.json")
    hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest() for name in paths}
    methods = (("district_driveway_context", measure_context),
               ("sidewalk_stop_evidence", measure_sidewalk_stop),
               ("pedestrian_precedence_evidence", measure_pedestrian),
               ("roadway_approach_evidence", measure_roadway))
    report = {"format": "worker-analysis-report", "measurements": {
        key: {"value": function(values, geometry), "method": function.__name__,
              "sources": hashes} for key, function in methods},
        "analysis_complete": True, "legal_verdict_claimed": False,
        "limitations": ["Synthetic fixture is software evidence only." if diagnostic else
                        "Original Native evidence requires independent physical and pixel review.",
                        "No legal cutoff is inferred from measured speed, distance or frame order."]}
    return report, inventory, sources, values, frames, diagnostic


def save_result(attempt, report, inventory, sources, values, frames, diagnostic):
    from worker_exchange.native_output import validate_result
    config = _read(attempt / "config.json")
    construction = _read(attempt / "construction.json")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    activities = sources["activity"]["samples"]
    geometry = sources["driveway_geometry"]
    provenance = {"source_kind": inventory["source_kind"],
                  "geometry_sha256": inventory["sources"]["driveway_geometry"]["sha256"],
                  "activity_sha256": inventory["sources"]["activity"]["sha256"]}
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame, activity in zip(frames, activities):
                if name == "driver_and_district_context":
                    value = {"ego_actor_id": geometry["ego_vehicle_id"],
                             "district": geometry["district"], "access": geometry["access"]}
                elif name == "driveway_sidewalk_roadway_geometry":
                    value = {"driveway_polygon_m": geometry["driveway_polygon_m"],
                             "sidewalk_polygon_m": geometry["sidewalk_polygon_m"],
                             "roadway_polygon_m": geometry["roadway_polygon_m"]}
                elif name == "ego_motion_and_body":
                    value = activity["ego"]
                elif name == "pedestrian_motion_and_body":
                    value = activity["pedestrian"] or {"present": False, "source": "original absence"}
                elif name == "approaching_vehicle_motion_and_body":
                    value = activity["roadway_vehicle"] or {"present": False, "source": "original absence"}
                elif name == "frame_map_and_cameras":
                    value = {"carla_frame": frame["carla_frame"], "video_frame": frame["video_frame"],
                             "camera_sources": sorted(inventory.get("media", {}))}
                else:
                    raise ValueError("unknown required driveway channel: " + name)
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_residential_driveway_context": provenance}) + "\n")
    for row in construction["recording_description"]["context_inputs"]:
        evidence.append({"name": row["name"], "unit": row["unit"],
                         "reference": str(context.relative_to(attempt))})
    motion_status = "unverified" if diagnostic else "met"
    physical_checks = {key: {
        "status": motion_status,
        "method": "source-joined original driveway samples; physical review remains local",
        "sources": {"original-attempt/" + name + ".json": digest
                    for name, digest in values["source_sha256"].items()},
        "available_intervals": [[frames[0]["time_s"], frames[-1]["time_s"]]],
        "detail": {"first_sidewalk_frame": values["first_sidewalk_frame"],
                   "first_roadway_frame": values["first_roadway_frame"],
                   "not_a_legal_threshold": True}}
        for key in ("setup", "target", "maneuver")}
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": {name: item["value"] for name, item in report["measurements"].items()},
        "target_checks": [{"target": "original residence driveway sidewalk-to-roadway sequence",
                           "requested": "source-bound original crossing",
                           "measured": values["first_roadway_frame"],
                           "method": "measure original frame-joined geometry and activity",
                           "tolerance": 0, "matched": True,
                           "physical_cause_confirmed": False,
                           "cause_evidence": values["source_sha256"]}],
        "setup_confirmed": not diagnostic,
        "behavior_attempted": not diagnostic,
        "maneuver_completed": not diagnostic,
        "termination_reason": "saved original driveway source measured; legal and physical review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {"original_driveway_measurements": values},
        "physical_checks": physical_checks,
        "provenance_kind": "synthetic_fixture" if diagnostic else "native",
        "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False,
    }
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    report, inventory, sources, values, frames, diagnostic = build(attempt)
    result = save_result(attempt, report, inventory, sources, values, frames, diagnostic)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    if (attempt / "result.json").exists() or args.output.exists():
        raise ValueError("refusing to replace saved original analysis")
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
