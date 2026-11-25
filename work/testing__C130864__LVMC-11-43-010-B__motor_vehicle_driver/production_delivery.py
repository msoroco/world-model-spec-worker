"""Audit a sealed original roundabout attempt and independent pixel review.

The audit reports observed source facts. It does not decide the legal gap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capture_roundabout import CAMERAS, CAMERA_DIMENSIONS
from independent_cpu_delivery import _decode
from roundabout_delivery_audit import audit_delivery
from roundabout_measurements import ASSIGNMENT_ID, SUFFIXES


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing original saved source: " + name)
    return path


def _read(root: Path, name: str) -> dict:
    return json.loads(_source(root, name).read_text())


def _review(root: Path, reference: dict) -> tuple[dict, str]:
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError("independent original review reference required")
    candidate = root / reference["path"]
    path = candidate.resolve()
    if not path.is_relative_to(root) or candidate.is_symlink() or not path.is_file():
        raise ValueError("independent original review must be within saved attempt")
    digest = _sha(path)
    if digest != reference.get("sha256"):
        raise ValueError("independent original review hash mismatch")
    return json.loads(path.read_text()), digest


def audit_original(attempt_dir: Path, case_id: str, review_ref: dict) -> dict:
    root = Path(attempt_dir).resolve()
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact roundabout case")
    receipt = _read(root, "original-receipt.json")
    native = _read(root, "native-seal.json")
    capture = _read(root, "capture-seal.json")
    if (receipt.get("case_id") != case_id or
            receipt.get("diagnostic_fixture") is not False or
            native.get("case_id") != case_id or
            native.get("restored") is not True or
            native.get("frame_count") != 900 or
            capture.get("format") != "worker-sealed-capture" or
            capture.get("provenance_kind") != "native" or
            capture.get("diagnostic_fixture") is not False or
            capture.get("frames") != 900 or
            capture.get("restoration", {}).get("restored") is not True or
            capture.get("events") !=
            ["capture_finished", "encoders_closed", "restoration_verified"]):
        raise ValueError("original Native provenance or restoration differs")
    hashes = {"map_packet_sha256": _sha(_source(root, "original-map.json")),
              "trace_sha256": _sha(_source(root, "original-trace.jsonl")),
              "source_receipt_sha256": _sha(_source(root, "original-receipt.json"))}
    if any(native.get(key) != value for key, value in hashes.items()):
        raise ValueError("original Native seal source binding differs")
    original = [json.loads(line) for line in
                _source(root, "original-trace.jsonl").read_text().splitlines()]
    graph = [json.loads(line) for line in _source(root, "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in
               _source(root, "video_frames.jsonl").read_text().splitlines()]
    if len(original) != len(graph) or len(graph) != len(mapping) or len(mapping) != 900:
        raise ValueError("original motion and frame map require 900 joined frames")
    for index, (motion, body, frame) in enumerate(zip(original, graph, mapping)):
        if (body.get("frame") != motion.get("frame") or
                frame.get("carla_frame") != motion.get("frame") or
                frame.get("native_frame") != motion.get("frame") or
                frame.get("video_frame") != index or
                abs(frame.get("time_s", -1) - motion.get("time_s", 1e9)) > 1e-4):
            raise ValueError("original motion/body/video time join differs")
    videos = {name: _decode(_source(root, name + ".mkv"),
                          CAMERA_DIMENSIONS[name], 900) for name in CAMERAS}
    if videos != native.get("video_sources_sha256") or set(
            capture.get("encoder_exit_codes", {})) != set(CAMERAS) or any(
                value != 0 for value in capture["encoder_exit_codes"].values()):
        raise ValueError("original encoded camera closure or source hashes differ")
    sealed = capture.get("sources", {})
    for name in ("original-map.json", "original-trace.jsonl",
                 "original-receipt.json", "trace.jsonl", "video_frames.jsonl",
                 *(camera + ".mkv" for camera in CAMERAS)):
        if sealed.get(name) != _sha(_source(root, name)):
            raise ValueError("canonical sealed source changed: " + name)
    measured = audit_delivery(case_id=case_id,
        map_path=root / "original-map.json",
        trace_path=root / "original-trace.jsonl",
        receipt_path=root / "original-receipt.json")
    review, review_sha = _review(root, review_ref)
    entry_frame = measured["first_observed_ego_entry_frame"]
    expected_wait = case_id.endswith("_wait")
    if expected_wait:
        if entry_frame is not None or review.get("ego_wait_observed") is not True:
            raise ValueError("requested wait not observed in original attempt")
    elif (type(entry_frame) is not int or
          measured["opponent_in_ring_at_ego_entry"] is not True or
          review.get("ego_entry_visible") is not True):
        raise ValueError("requested entry with circulating opponent not observed")
    reviewed_frames = [0, 899] if expected_wait else [0, entry_frame, 899]
    if (review.get("format") != "independent-original-roundabout-review" or
            review.get("case_id") != case_id or
            review.get("source") != "original_four_camera_video" or
            review.get("diagnostic_fixture") is not False or
            not review.get("reviewer") or not review.get("method") or
            review.get("full_original_video_reviewed") is not True or
            review.get("reviewed_camera_names") != list(CAMERAS) or
            review.get("reviewed_frame_ids") != reviewed_frames or
            review.get("native_seal_sha256") != _sha(root / "native-seal.json") or
            review.get("capture_seal_sha256") != _sha(root / "capture-seal.json") or
            review.get("map_sha256") != hashes["map_packet_sha256"] or
            review.get("trace_sha256") != hashes["trace_sha256"] or
            review.get("video_sha256") != videos or
            review.get("ego_visible_in_original_views") is not True or
            review.get("opponent_visible_in_original_views") is not True or
            review.get("roundabout_geometry_visible") is not True or
            review.get("observed_ego_entry_frame") != entry_frame or
            review.get("opponent_in_ring_at_entry") is not
            measured["opponent_in_ring_at_ego_entry"] or
            review.get("opponent_in_conflict_at_entry") is not
            measured["opponent_in_conflict_at_ego_entry"]):
        raise ValueError("independent physical review not bound to original roundabout sources")
    return {**measured, "native_seal_sha256": _sha(root / "native-seal.json"),
            "capture_seal_sha256": _sha(root / "capture-seal.json"),
            "encoded_camera_source_sha256": videos,
            "independent_review_sha256": review_sha,
            "original_attempt_audited": True, "actual_pixels": True,
            "physical_completion": True,
            "legal_gap_judgment": "unresolved",
            "physical_acceptance": False, "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--physical-review-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_original(args.attempt, args.case_id,
                            json.loads(args.physical_review_ref.read_text()))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
