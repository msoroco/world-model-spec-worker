"""Saved-only sidewalk movement, entrance and context measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sidewalk_case import BY_SUFFIX, validate_case_site
from sidewalk_measure import measure_frame, polygon

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def verify_join(history, mapping, trace):
    if not history or len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError("body, trace and camera frame counts differ")
    for index, (body, camera, telemetry) in enumerate(zip(history, mapping, trace)):
        if (body["original_frame"] != camera["carla_frame"] or
                body["original_frame"] != telemetry["frame"] or
                abs(body["time_s"] - camera["time_s"]) > 1e-4 or
                abs(body["time_s"] - telemetry["time_s"]) > 1e-4 or
                camera["video_frame"] != index):
            raise ValueError("original body, trace and camera frames disagree")


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    suffix = case_id.split("__")[-1]
    case = BY_SUFFIX.get(suffix)
    if case is None:
        raise ValueError("exact sidewalk case missing")
    description = config["case"]["recording_description"]
    original = (root / "acquisition.json").is_file()
    names = ("sidewalk-history.jsonl", "sidewalk-site.json", "trace.jsonl",
             "video_frames.jsonl", "road.xodr", "carla_recorder.log",
             *[name + ".mkv" for name in CAMERAS])
    if original:
        acquisition = json.loads(required(root, "acquisition.json").read_text())
        for name in names:
            if (acquisition.get(name, {}).get("kind") != "original_native" or
                    acquisition[name].get("sha256") != sha(required(root, name))):
                raise ValueError("original Native source changed: " + name)
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
        if (provenance.get("provenance_kind") != "native" or
                provenance.get("diagnostic_fixture") is not False):
            raise ValueError("original Native provenance missing")
        archived = required(root, "reviewed-site-packet/site.json")
        if sha(archived) != acquisition["reviewed-site-packet/site.json"]["sha256"]:
            raise ValueError("reviewed original sidewalk packet changed")
    else:
        marker = json.loads(required(root, "diagnostic-source-note.json").read_text())
        if (marker.get("source_kind") != "synthetic_diagnostic_fixture" or
                marker.get("accepted_original_source") is not False or
                marker.get("case_id") != case_id):
            raise ValueError("synthetic compatibility provenance missing")
    site = json.loads(required(root, "sidewalk-site.json").read_text())
    polygon(site.get("sidewalk_area_polygon_xy"))
    validate_case_site(case, site)
    history = rows(required(root, "sidewalk-history.jsonl"))
    mapping = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    verify_join(history, mapping, trace)
    measurements = [measure_frame(row, site) for row in history]
    if any(row["vehicle_actor_id"] != history[0]["vehicle_actor_id"] for row in history):
        raise ValueError("original vehicle identity changes during travel")
    if original and any(row["body_geometry_source_sha256"] != site["body_geometry_source_sha256"]
                        for row in history):
        raise ValueError("original body design source changes during travel")
    peak_sidewalk = max(row["sidewalk_overlap_area_m2"] for row in measurements)
    peak_entrances = {kind: max(row["entrance_overlap_area_m2"][kind] for row in measurements)
                      for kind in site["entrance_polygons_xy"]}
    if not original:
        if case.travel_region == "road" and peak_sidewalk > 0:
            raise ValueError("diagnostic road body intersects sidewalk")
        if case.travel_region == "sidewalk" and peak_sidewalk <= 0:
            raise ValueError("diagnostic sidewalk body has no sidewalk contact")
        if case.entrance_kind and peak_entrances[case.entrance_kind] <= 0:
            raise ValueError("diagnostic body misses selected entrance")
    measured = {"case_id": suffix, "frame_count": len(history),
                "maximum_sidewalk_body_overlap_m2": peak_sidewalk,
                "maximum_entrance_body_overlap_m2": peak_entrances,
                "vehicle_design": site["vehicle_design"],
                "operator_context": site["operator_context"],
                "diagnostic_fixture": not original,
                "legal_judgment": None,
                "measurement_limit": "Areas and authored context are separate; no legal overlap cutoff or duty inference."}
    source_names = ("sidewalk-site.json", "sidewalk-history.jsonl",
                    "video_frames.jsonl", "trace.jsonl")
    sources = {name: sha(root / name) for name in source_names}
    channel_values = {
        "sidewalk_boundary": lambda row: site["sidewalk_area_polygon_xy"],
        "pedestrian_purpose": lambda row: site["pedestrian_purpose"],
        "body_footprint_history": lambda row: row["body_polygon_xy"],
        "vehicle_motion_history": lambda row: {"position_m": row["position_m"],
                                                 "speed_mps": row["ego_speed_mps"],
                                                 "control": row["control_command"]},
        "entrance_geometry": lambda row: site["entrance_polygons_xy"],
        "vehicle_design": lambda row: site["vehicle_design"],
        "operator_duty": lambda row: site["operator_context"],
        "frame_map": lambda row: {"frame": row["original_frame"], "time_s": row["time_s"]},
        "four_camera_video": lambda row: [name + ".mkv" for name in CAMERAS],
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in channel_values:
            raise ValueError("unknown sidewalk channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                           "value": channel_values[name](row)}) + "\n"
                                    for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": path.name})
    context = {}
    for item in description["context_inputs"]:
        name = item["name"]
        value = site.get(name)
        context[name] = {"value": value,
                         "source": site.get(name + "_source_sha256"),
                         "status": "original_review_pending" if original else "synthetic_diagnostic"}
    context_path = root / "channel-context.json"
    context_path.write_text(json.dumps(context) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "original sidewalk travel and independent exception sources",
                                 "requested": config["case"], "measured": measured,
                                 "method": "original source-bound geometry" if original else "synthetic diagnostic geometry",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "Independent physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": not original,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    report_values = {}
    requirements = json.loads(required(root, "measurement-contract.json").read_text())["requirements"]
    for item in requirements:
        report_values[item["output_key"]] = {
            "method": item["method"], "value": measured,
            "sources": {name: sha(required(root, name)) for name in item["inputs"]}}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": report_values,
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Original sidewalk purpose, vehicle/duty and pixels require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
