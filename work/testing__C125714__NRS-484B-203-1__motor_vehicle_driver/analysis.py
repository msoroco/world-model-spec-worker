"""Saved-only opposing-pass measurement and original camera/source audit.

No requested route or fixture label is used as a measurement. The report keeps
physical and legal outcomes unresolved until separate local acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_history import audit_media
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
            "paved_width_range_m": observed["paved_width_range_m"]}


def constraint_context_measurement(reviewed_map):
    feature = reviewed_map.get("physical_constraint")
    if not isinstance(feature, dict) or not feature.get("source_id"):
        raise ValueError("source-recorded physical constraint context missing")
    return {"feature_source_id": feature["source_id"],
            "station_range_m": feature["station_range_m"],
            "lateral_range_m": feature["lateral_range_m"],
            "legal_reasonableness": "unresolved"}


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
            "constraint_context": {"value": constraint_context_measurement(reviewed),
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    target = Path(args.output)
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
