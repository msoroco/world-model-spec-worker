"""Saved-only original Fremont source, device, conduct and sidewalk measurements."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from fremont_180 import AID, BY_SUFFIX, measure_original, need

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def source_bound_fremont_measurement(value: object) -> dict:
    """Explicit object-valued measurement method bound by the contract."""
    need(isinstance(value, dict), "Fremont measurement object missing")
    return value


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    cfg = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = cfg["selected_case_id"]
    need(case_id.startswith(AID + "__"), "exact Fremont assignment differs")
    case = BY_SUFFIX.get(case_id.removeprefix(AID + "__"))
    need(case is not None, "exact Fremont case missing")
    original = (root / "acquisition.json").is_file()
    source_names = ("fremont-history.jsonl", "fremont-site.json", "trace.jsonl",
                    "video_frames.jsonl")
    if original:
        acquisition = json.loads(required(root, "acquisition.json").read_text())
        for name in (*source_names, "road.xodr", "carla_recorder.log",
                     *[name + ".mkv" for name in CAMERAS]):
            need(acquisition.get(name, {}).get("kind") == "original_native"
                 and acquisition[name].get("sha256") == sha(required(root, name)),
                 "original Native source changed: " + name)
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
        need(provenance.get("provenance_kind") == "native"
             and provenance.get("diagnostic_fixture") is False,
             "original Native provenance missing")
        need(sha(required(root, "reviewed-fremont-packet/site.json")) ==
             acquisition["reviewed-fremont-packet/site.json"]["sha256"],
             "reviewed original Fremont packet changed")
    else:
        marker = json.loads(required(root, "diagnostic-source-note.json").read_text())
        need(marker.get("source_kind") == "synthetic_diagnostic_fixture"
             and marker.get("accepted_original_source") is False
             and marker.get("case_id") == case_id,
             "synthetic compatibility provenance missing")
    site = json.loads(required(root, "fremont-site.json").read_text())
    need(site.get("municipality") == "Las Vegas"
         and site.get("street") == "Fremont Street"
         and site.get("from_cross_street") == "Main Street"
         and site.get("to_cross_street") == "Seventh Street",
         "Fremont exact geographic source missing")
    need(site.get("device", {}).get("kind") == case.device_kind
         and site.get("operator_conduct", {}).get("kind") == case.conduct,
         "original device or conduct differs from selected case")
    history = rows(required(root, "fremont-history.jsonl"))
    mapping = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    need(history and len(history) == len(mapping) == len(trace),
         "original history, trace and video frame counts differ")
    for index, (row, frame, telemetry) in enumerate(zip(history, mapping, trace)):
        need(row["original_frame"] == frame["carla_frame"] == telemetry["frame"]
             and abs(row["time_s"] - frame["time_s"]) <= 1e-4
             and abs(row["time_s"] - telemetry["time_s"]) <= 1e-4
             and frame["video_frame"] == index,
             "original Fremont trace and video frames disagree")
    measured = measure_original(history, site, case)
    measured["diagnostic_fixture"] = not original
    source_hashes = {name: sha(required(root, name)) for name in source_names}
    description = cfg["case"]["recording_description"]
    values = {
        "device_qualification": lambda row: site["device"],
        "riding_conduct": lambda row: site["operator_conduct"],
        "surface_occupancy": lambda row: {"point": row["position_xy"],
                                           "selected_sidewalk": row.get("on_selected_sidewalk")},
        "municipal_extent": lambda row: site["longitudinal_station_m"],
        "area_signs": lambda row: site["sign_inventory"],
        "original_frame_join": lambda row: {"frame": row["original_frame"],
                                             "time_s": row["time_s"]},
        "four_camera_video": lambda row: [name + ".mkv" for name in CAMERAS],
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        need(name in values, "unknown Fremont channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                           "value": values[name](row)}) + "\n"
                                    for row in history), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": path.name})
    context = {"reviewed_municipal_context":
               {"municipality": site["municipality"], "street": site["street"],
                "main_to_seventh": site["longitudinal_station_m"],
                "source_status": "original_review_pending" if original else
                                 "synthetic_diagnostic"}}
    (root / "channel-context.json").write_text(json.dumps(context) + "\n",
                                               encoding="utf-8")
    evidence.append({"name": "reviewed_municipal_context", "unit": "source record",
                     "reference": "channel-context.json"})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "original Fremont sidewalk and riding source",
                                 "requested": cfg["case"], "measured": measured,
                                 "method": "original source-bound geometry" if original else
                                           "synthetic diagnostic geometry",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": source_hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Independent physical and sign review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": not original,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    contract = json.loads(required(root, "measurement-contract.json").read_text())
    reports = {item["output_key"]:
               {"method": item["method"], "value": source_bound_fremont_measurement(measured),
                "sources": {name: sha(required(root, name)) for name in item["inputs"]}}
               for item in contract["requirements"]}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": reports, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Original map, device, walking motion, signage and pixels need independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior Fremont analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n",
                           encoding="utf-8")
