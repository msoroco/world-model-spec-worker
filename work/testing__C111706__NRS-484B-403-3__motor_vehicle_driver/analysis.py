"""Saved U-turn finalizer; diagnostic inputs never assert physical or legal success."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_uturn import analyze_native


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + relative)
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def measure_uturn(measured: dict, site: dict) -> dict:
    """Report source measurements without applying a legal U-turn predicate."""
    return {"reversal_deg": measured["reversal_deg"],
            "whole_body_inside_intersection_frames":
                measured["whole_body_inside_intersection_frames"],
            "minimum_other_vehicle_center_distance_m":
                measured["minimum_other_vehicle_center_distance_m"],
            "district_review_source_sha256": site["district_source_sha256"],
            "intersection_boundary_source_sha256":
                measured["intersection_boundary_source_sha256"],
            "statutory_district_classification": "unresolved_review",
            "physical_completion": "unconfirmed"}


def source(root: Path):
    index_path = required(root, "capture/source-index.json")
    index = read(index_path)
    if index.get("format") not in (
            "c111706-diagnostic-source-index-v1",
            "c111706-native-source-index-v1"):
        raise ValueError("U-turn source index format differs")
    case = read(required(root, "config.json"))["selected_case_id"]
    if index.get("case_id") != case:
        raise ValueError("U-turn source index case differs")
    diagnostic = index["format"] == "c111706-diagnostic-source-index-v1"
    sources = {}
    for name in ("site.json", "native-uturn.json"):
        rel = "capture/" + name
        path = required(root, rel)
        item = index.get("files", {}).get(name, {})
        if (item.get("sha256") != digest(path) or
                item.get("source") != ("diagnostic_synthetic" if diagnostic else "native_original")):
            raise ValueError("U-turn original source binding differs: " + name)
        sources[name] = path
    site = read(sources["site.json"])
    native = read(sources["native-uturn.json"])
    if site.get("case_id") != case or native.get("case_id") != case:
        raise ValueError("U-turn exact site/Native case differs")
    if native.get("site_sha256") != digest(sources["site.json"]):
        raise ValueError("U-turn site/Native source join differs")
    if (native.get("map_sha256") != site.get("map_sha256") or
            native.get("route_sha256") != site.get("route_sha256") or
            native.get("district_basis", {}).get("source_sha256") != site.get("district_source_sha256") or
            native.get("intersection_boundary") != site.get("intersection_boundary")):
        raise ValueError("U-turn map, route, district or boundary source differs")
    if not diagnostic and site.get("source_kind") != "original_native_site_review":
        raise ValueError("original reviewed U-turn site required")
    measured = analyze_native(sources["native-uturn.json"],
                              expected_case=case,
                              expected_sha256=digest(sources["native-uturn.json"]))
    expected_count = 9 if diagnostic else 900
    if measured["frame_count"] != expected_count:
        raise ValueError("U-turn source frame count differs")
    inside = bool(measured["whole_body_inside_intersection_frames"])
    if inside == case.endswith("__approach_before_intersection"):
        raise ValueError("measured U-turn location differs from exact case")
    return index, site, native, measured, sources, diagnostic


def build_report(root: Path):
    root = Path(root).resolve()
    index, site, native, measured, sources, diagnostic = source(root)
    case = index["case_id"]
    selected = {"uturn_source_measurement": {
        "method": "measure_uturn", "value": measure_uturn(measured, site),
        "sources": {"capture/site.json": digest(sources["site.json"]),
                    "capture/native-uturn.json": digest(sources["native-uturn.json"])}}}
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "measurements": selected,
            "source_index_sha256": digest(root / "capture/source-index.json"),
            "provenance_kind": "synthetic_fixture" if diagnostic else "original_saved_source",
            "diagnostic_fixture": diagnostic,
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False,
            "limitations": ["Business-district and statutory intersection classification remain independent review.",
                            "Sampled body containment does not establish continuous swept occupancy.",
                            "CARLA physical motion and original pixels require independent review."]}


def build_result(root: Path, report: dict):
    """Retain the exact source-frame join for the pinned converter and media audit."""
    root = Path(root).resolve()
    config = read(required(root, "config.json"))
    index, site, native, measured, sources, diagnostic = source(root)
    frames = native["frames"]
    count = len(frames)
    trace_path = required(root, "trace.jsonl")
    frame_map_path = required(root, "video_frames.jsonl")
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_map_path.read_text().splitlines()]
    if len(trace) != count or len(frame_map) != count:
        raise ValueError("U-turn trace/video source frame count differs")
    if [r["frame"] for r in trace] != [f["frame"] for f in frames] or [
            r["carla_frame"] for r in frame_map] != [f["frame"] for f in frames]:
        raise ValueError("U-turn original frame join differs")
    for name in VIEWS:
        required(root, name + ".mkv")
    description = config["case"]["recording_description"]
    context = site
    values = {
        "business_district": lambda frame: {"district_source_sha256": site["district_source_sha256"],
                                             "classification": "unresolved_review"},
        "intersection_exception": lambda frame: {"boundary_source_sha256": site["intersection_boundary_source_sha256"],
                                                   "ego_body_corners_xy_m": frame["ego"]["body_corners_xy_m"]},
        "vehicle_reversal": lambda frame: {"ego_yaw_deg": frame["ego"]["yaw_deg"],
                                             "ego_lane_id": frame["ego"]["lane_id"]},
        "surrounding_vehicle": lambda frame: {"other_vehicle": frame["other_vehicle"],
                                                "ego": {"x": frame["ego"]["x"], "y": frame["ego"]["y"]}},
        "camera_frame_map": lambda frame: {"native_frame": frame["frame"],
                                            "camera_views": list(VIEWS)},
    }
    evidence = []
    for number, channel in enumerate(description["channels"]):
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented U-turn recording channel: " + name)
        reference = f"recording-channel-{number}.jsonl"
        with (root / reference).open("w", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps({"time_s": frame["time_s"],
                                         "value": values[name](frame)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": reference})
    for number, item in enumerate(description["context_inputs"]):
        if item["name"] != "reviewed_original_site":
            raise ValueError("unimplemented U-turn recording context")
        reference = f"recording-context-{number}.json"
        write(root / reference, {item["name"]: context})
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": reference})
    result = {"case_id": report["case_id"],
              "measured_values": {key: value["value"] for key, value in report["measurements"].items()},
              "target_checks": [{"target": "source_sealed_observation_count",
                                  "requested": count, "measured": count,
                                  "method": "original frame and video join", "tolerance": 0,
                                  "matched": True, "physical_cause_confirmed": False,
                                  "cause_evidence": "original physical realization unverified"}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "saved source processing; physical completion unverified",
              "physical_failure_flags": ["physical_completion_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description,
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": report["provenance_kind"],
              "diagnostic_fixture": diagnostic,
              "legal_verdict_claimed": False,
              "physical_acceptance_claimed": False}
    if (root / "result.json").exists():
        raise ValueError("Retain prior result; use a fresh analysis attempt")
    write(root / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    build_result(args.attempt, report)
    write(args.output, report)


if __name__ == "__main__":
    main()
