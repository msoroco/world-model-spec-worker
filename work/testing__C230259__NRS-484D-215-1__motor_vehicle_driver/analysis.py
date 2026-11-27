"""Saved-only source-bound measurements for NRS 484D.215(1).

This module never starts CARLA, changes original evidence or applies a legal
beam/glare threshold. It rejects stale Native sources and missing original
participant, pixel and frame-join evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from beam_measure import measure as measure_motion
from beam_pixels import measure as measure_pixels

ASSIGNMENT = "testing__C230259__NRS-484D-215-1__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _path(root: Path, name: str) -> Path:
    if name != Path(name).name or name in ("", ".", ".."):
        raise ValueError("original source path must be attempt-relative")
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _hash(root: Path, name: str) -> str:
    return hashlib.sha256(_path(root, name).read_bytes()).hexdigest()


def _measurement(value: dict, method: str, root: Path, names: tuple[str, ...]) -> dict:
    return {"value": value, "method": method,
            "sources": {name: _hash(root, name) for name in names}}


def measure_qualifying(motion: dict) -> dict:
    return {"observed_qualifying_frames": motion["frame_count"],
            "reviewed_time_source": True, "reviewed_highway_source": True,
            "legal_applicability_verdict": None}


def measure_revelation(motion: dict, pixels: dict) -> dict:
    return {"person_distance_m_by_frame": [x["person_center_distance_m"] for x in motion["rows"]],
            "vehicle_distance_m_by_frame": [x["target_vehicle_center_distance_m"] for x in motion["rows"]],
            "person_luma_8bit_by_frame": [x["person_mean_luma_8bit"] for x in pixels["rows"]],
            "vehicle_luma_8bit_by_frame": [x["target_vehicle_mean_luma_8bit"] for x in pixels["rows"]],
            "safe_distance_verdict": None}


def measure_oncoming_distance(motion: dict) -> dict:
    within = [x for x in motion["rows"] if x["body_gap_within_500_ft"] or x["eye_gap_within_500_ft"]]
    return {"oncoming_body_gap_m_by_frame": [x["oncoming_body_gap_m"] for x in motion["rows"]],
            "oncoming_eye_gap_m_by_frame": [x["oncoming_eye_gap_m"] for x in motion["rows"]],
            "within_500ft_frame_count": len(within),
            "distance_endpoint_interpretation": None}


def measure_glare(motion: dict, pixels: dict) -> dict:
    return {"oncoming_eye_luma_8bit_by_frame": [x.get("oncoming_eye_mean_luma_8bit") for x in pixels["rows"]],
            "lamp_readback_bits_by_frame": [x["lamp_state_bits"] for x in motion["rows"]],
            "physical_glare_verdict": None}


def measure_lowermost(case: dict) -> dict:
    return {"requested_beam": case["requested_beam"],
            "requested_contour": case["requested_contour"],
            "requested_load": case["requested_load"],
            "lowermost_specification_confirmed": False,
            "deemed_glare_verdict": None}


def build(attempt: Path, *, expected_frames: int = 900,
          diagnostic: bool = False) -> dict:
    root = Path(attempt).resolve(strict=True)
    config = json.loads(_path(root, "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484D-215-1"):
        raise ValueError("saved exact beam case differs")
    case = config.get("case_plan")
    if not isinstance(case, dict) or case.get("case_id") != case_id:
        raise ValueError("saved exact case plan missing")
    site = json.loads(_path(root, "site-packet.json").read_text())
    if (site.get("case_id") != case_id or
            site.get("requested_beam") != case.get("requested_beam") or
            site.get("requested_contour") != case.get("requested_contour") or
            site.get("requested_load") != case.get("requested_load") or
            site.get("requested_start_body_gap_ft") != case.get("requested_start_body_gap_ft")):
        raise ValueError("saved original site does not bind exact case")
    receipt = json.loads(_path(root, "native-source-receipt.json").read_text())
    if not diagnostic and expected_frames != 900:
        raise ValueError("original Native delivery requires 900 frames")
    if (receipt.get("format") != "beam-road-native-source-v1" or
            receipt.get("case_id") != case_id or
            receipt.get("frame_count") != expected_frames or
            receipt.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved Native source receipt differs")
    source_names = ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")
    sources = {name: _hash(root, name) for name in source_names}
    if receipt.get("source_hashes") != sources:
        raise ValueError("saved original geometry/beam source hashes differ")
    pixel_media_extension = ".mkv" if "approach.mkv" in receipt.get("pixel_source_hashes", {}) else ".zip"
    pixel_names = ("roi-frames.jsonl", "camera-frame-map.jsonl",
                   "approach" + pixel_media_extension, "driver_reference" + pixel_media_extension)
    pixel_sources = {name: _hash(root, name) for name in pixel_names}
    if receipt.get("pixel_source_hashes") != pixel_sources:
        raise ValueError("saved original pixel source hashes differ")
    media = receipt.get("camera_movies")
    if not isinstance(media, dict) or set(media) != set(VIEWS):
        raise ValueError("four original video sources required")
    for view, source in media.items():
        if (source.get("path") != view + ".mkv" or
                source.get("sha256") != _hash(root, source["path"]) or
                source.get("source_frame_count") != expected_frames):
            raise ValueError("saved original camera movie differs: " + view)
    motion = measure_motion(root, sources, expected_frames=expected_frames, case=case)
    pixels = measure_pixels(root, pixel_sources, expected_frames=expected_frames,
                            diagnostic=diagnostic, include_eye=case["branch"] == "oncoming")
    if [x["original_frame"] for x in motion["rows"]] != [x["original_frame"] for x in pixels["rows"]]:
        raise ValueError("saved motion and original pixels have different frame IDs")
    values = {}
    values["beam_requirement_0"] = _measurement(
        measure_qualifying(motion), "measure_qualifying",
        root, ("site-packet.json", "actor-state.jsonl", "camera-frame-map.jsonl"))
    values["beam_requirement_1"] = _measurement(
        measure_revelation(motion, pixels), "measure_revelation",
        root, ("actor-state.jsonl", "roi-frames.jsonl", "approach" + pixel_media_extension, "camera-frame-map.jsonl"))
    values["beam_requirement_2"] = _measurement(
        measure_oncoming_distance(motion), "measure_oncoming_distance",
        root, ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json"))
    values["beam_requirement_3"] = _measurement(
        measure_glare(motion, pixels), "measure_glare",
        root, ("roi-frames.jsonl", "driver_reference" + pixel_media_extension, "camera-frame-map.jsonl",
               "actor-state.jsonl"))
    values["beam_requirement_4"] = _measurement(
        measure_lowermost(case), "measure_lowermost",
        root, ("site-packet.json", "actor-state.jsonl", "roi-frames.jsonl"))
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": values, "analysis_complete": True,
            "original_frame_count": motion["frame_count"],
            "legal_verdict_claimed": False,
            "limitations": ["Original RGB luma is not calibrated road illuminance or physical ray projection into eyes.",
                            "CARLA low-beam readback alone does not certify the statutory lowermost distribution.",
                            "No numeric safe-distance or glare threshold is supplied."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("saved analysis output already exists")
    receipt = json.loads(_path(Path(args.attempt), "native-source-receipt.json").read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    if not diagnostic and receipt.get("frame_count") != 900:
        raise ValueError("original Native delivery requires 900 frames")
    report = build(Path(args.attempt), expected_frames=receipt.get("frame_count", 900),
                   diagnostic=diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    from beam_publication import publish
    from worker_exchange.native_output import physical_result, write_result
    result = publish(Path(args.attempt), expected_frames=receipt.get("frame_count", 900),
                     diagnostic=diagnostic)
    write_result(Path(args.attempt), physical_result(Path(args.attempt), result))


if __name__ == "__main__":
    main()
