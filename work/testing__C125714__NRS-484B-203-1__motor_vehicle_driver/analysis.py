"""Saved-only opposing-pass measurement and original camera/source audit.

No requested route or fixture label is used as a measurement. The report keeps
physical and legal outcomes unresolved until separate local acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native_history import CAMERA_DIMENSIONS, audit_media
from opposing_pass import load_sealed, measure
from physical_completion import assess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _required(attempt, name):
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def opposing_motion_measurement(trace):
    return {"opposing_travel_during_pass": True,
            "passing_frames": measure(trace)["passing_frames"],
            "right_of_other_all": measure(trace)["right_of_other_all"]}


def paved_allocation_measurement(trace):
    observed = measure(trace)
    return {"ego_edge_from_paved_half_max_m": observed["ego_north_edge_from_half_max_m"],
            "other_edge_from_paved_half_max_m": observed["other_south_edge_from_half_max_m"],
            "ego_yielded_paved_fraction_min": observed["ego_yielded_paved_fraction_min"],
            "other_yielded_paved_fraction_min": observed["other_yielded_paved_fraction_min"],
            "paved_width_range_m": observed["paved_width_range_m"]}


def constraint_context_measurement(reviewed_map, variant):
    feature = reviewed_map.get("physical_constraint")
    if feature is None and variant != "right_constrained":
        return {"feature_present": False, "legal_reasonableness": "unresolved"}
    if not isinstance(feature, dict) or not feature.get("source_id"):
        raise ValueError("source-recorded physical constraint context missing")
    return {"feature_present": True, "feature_source_id": feature["source_id"],
            "station_range_m": feature["station_range_m"],
            "lateral_range_m": feature["lateral_range_m"],
            "legal_reasonableness": "unresolved"}


def audit_diagnostic_videos(trace, attempt, expected_manifest_sha256):
    """Join labeled synthetic actor clocks to generated videos; no physical claim."""
    manifest_path = _required(attempt, "opposing-camera-frames/camera-manifest.json")
    if sha(manifest_path) != expected_manifest_sha256:
        raise ValueError("diagnostic camera manifest changed")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("format") != "diagnostic-video-join":
        raise ValueError("diagnostic video manifest required")
    rows = manifest.get("rows")
    samples = trace.get("samples")
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("diagnostic camera/actor frame count mismatch")
    for i, (actor, camera) in enumerate(zip(samples, rows)):
        if any(camera.get(key) != actor.get(key) for key in
               ("frame", "time_s", "native_frame", "native_elapsed_s")):
            raise ValueError(f"diagnostic camera/actor clock mismatch at {i}")
    if manifest.get("videos") != {name: name + ".mkv" for name in CAMERA_DIMENSIONS}:
        raise ValueError("four diagnostic videos required")
    for name, (width, height) in CAMERA_DIMENSIONS.items():
        video = _required(attempt, manifest["videos"][name])
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames,width,height", "-of", "json", str(video)],
                               capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or (streams[0].get("width"), streams[0].get("height")) != (width, height) or int(streams[0].get("nb_read_frames", -1)) != len(rows):
            raise ValueError("diagnostic video decode/profile mismatch: " + name)
    return {"trace_sha256": sha(_required(attempt, "opposing-actor-trace.json")),
            "camera_manifest_sha256": expected_manifest_sha256,
            "joined_frames": len(rows), "decoded_view_frames": len(rows)*4,
            "diagnostic_fixture": True, "physical_acceptance": False,
            "legal_judgment": "unresolved"}


def build_report(attempt, *, diagnostic_fixture=False, camera_dimensions=None):
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("selected_case_id")
    variant = config.get("variant")
    if case != config.get("assignment_id", "") + "__" + str(variant):
        raise ValueError("saved exact case identity changed")
    receipt_path = _required(attempt, "opposing-capture-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    trace_path = _required(attempt, "opposing-actor-trace.json")
    if sha(trace_path) != receipt.get("sha256"):
        raise ValueError("original actor trace changed after capture")
    trace = load_sealed(trace_path, receipt["sha256"])
    if trace.get("variant") != variant:
        raise ValueError("original actor trace selected another case")
    if trace.get("diagnostic_fixture") is not diagnostic_fixture:
        raise ValueError("diagnostic and original Native provenance differ")
    if not diagnostic_fixture and (receipt.get("frame_count") != 900 or
            len(trace.get("samples", [])) != 900):
        raise ValueError("original 900-frame acquisition incomplete")
    map_path = _required(attempt, "reviewed-map.json")
    if sha(map_path) != trace.get("map_sha256"):
        raise ValueError("retained reviewed map source changed")
    reviewed = load_sealed(map_path, trace["map_sha256"])
    if not diagnostic_fixture and (reviewed.get("source_kind") != "original_native_map_geometry" or
            not reviewed.get("reviewed_provenance")):
        raise ValueError("original reviewed map context missing")
    manifest = receipt.get("camera_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("original four-camera manifest missing")
    media = attempt / "opposing-camera-frames"
    camera_packet = json.loads(_required(attempt, "opposing-camera-frames/camera-manifest.json").read_text())
    if diagnostic_fixture and isinstance(camera_packet, dict):
        media_audit = audit_diagnostic_videos(trace, attempt, manifest["sha256"])
    else:
        media_audit = audit_media(trace_path, receipt["sha256"], media,
                                  manifest["sha256"], dimensions=camera_dimensions)
    if media_audit["joined_frames"] != receipt["frame_count"]:
        raise ValueError("original actor and camera count differs")
    measured = measure(trace)
    physical = assess(trace_path, receipt["sha256"])
    trace_sha, map_sha, camera_sha = receipt["sha256"], sha(map_path), manifest["sha256"]
    return {"format": "worker-analysis-report", "case_id": case,
        "measurements": {"opposing_pass_measurement": {
            "value": measured,
            "method": "original 20 Hz opposing body overlap and reviewed paved boundaries",
            "sources": {"opposing-actor-trace.json": trace_sha,
                "opposing-camera-frames/camera-manifest.json": camera_sha,
                "reviewed-map.json": map_sha}},
            "opposing_motion": {"value": opposing_motion_measurement(trace),
                "method": "opposing_motion_measurement",
                "sources": {"opposing-actor-trace.json": trace_sha,
                    "opposing-camera-frames/camera-manifest.json": camera_sha}},
            "paved_allocation": {"value": paved_allocation_measurement(trace),
                "method": "paved_allocation_measurement",
                "sources": {"opposing-actor-trace.json": trace_sha,
                    "reviewed-map.json": map_sha}},
            "constraint_context": {"value": constraint_context_measurement(reviewed, variant),
                "method": "constraint_context_measurement",
                "sources": {"reviewed-map.json": map_sha}}},
        "camera_audit": media_audit, "analysis_complete": True,
        "physical_checks": physical["physical_checks"],
        "maneuver_completed": physical["maneuver_completed"],
        "realized_observables": physical["realized_observables"],
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
        "limitations": ["Diagnostic fixture proves software checks only." if diagnostic_fixture
                        else "Original camera pixels and realized passing require independent local review.",
                        "As nearly as possible remains a human legal judgment."]}


def write_selected_result(attempt, report):
    """Project sealed saved sources into the exact recording contract once."""
    attempt = Path(attempt)
    config = json.loads(_required(attempt, "config.json").read_text())
    description = config["recording_description"]
    traces = json.loads(_required(attempt, "opposing-actor-trace.json").read_text())
    cameras = json.loads(_required(attempt, "opposing-camera-frames/camera-manifest.json").read_text())
    _required(attempt, "trace.jsonl")
    _required(attempt, "video_frames.jsonl")
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        _required(attempt, name + ".mkv")
    camera_rows = cameras["rows"] if isinstance(cameras, dict) and cameras.get("format") == "diagnostic-video-join" else cameras
    if len(traces["samples"]) != len(camera_rows):
        raise ValueError("saved recording channel lengths differ")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    streams = {
        "opposing_actor_body_history": traces["samples"],
        "four_camera_views": camera_rows,
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("selected recording channel has no saved source: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as output:
            for row in streams[name]:
                output.write(json.dumps({"time_s": row["time_s"], "value": row},
                                        separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    contexts = {"reviewed_median_opening_map": json.loads(
        _required(attempt, "reviewed-map.json").read_text())}
    for context in description["context_inputs"]:
        name = context["name"]
        if name not in contexts:
            raise ValueError("selected context has no saved source: " + name)
        path = channels / (name + ".json")
        path.write_text(json.dumps({name: contexts[name]}, separators=(",", ":"),
                                   allow_nan=False) + "\n", encoding="utf-8")
        evidence.append({"name": name, "unit": context["unit"],
                         "reference": str(path.relative_to(attempt))})
    measurements = {name: item["value"] for name, item in report["measurements"].items()}
    target = {"target": "original opposing-body and four-camera observation",
              "requested": True, "measured": True, "method": "build_report",
              "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
              "cause_evidence": report["measurements"]["opposing_motion"]["sources"]}
    result = {"case_id": report["case_id"], "measured_values": measurements,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source projection; original physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result_path = attempt / "result.json"
    if result_path.exists():
        raise FileExistsError(result_path)
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt)
    provenance = json.loads(_required(attempt, "acquisition-provenance.json").read_text())
    diagnostic = (provenance.get("provenance_kind") == "synthetic_fixture" and
                  provenance.get("diagnostic_fixture") is True)
    if provenance.get("provenance_kind") not in ("synthetic_fixture", "native"):
        raise ValueError("saved acquisition provenance missing")
    report = build_report(attempt, diagnostic_fixture=diagnostic)
    write_selected_result(args.attempt, report)
    target = Path(args.output)
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
