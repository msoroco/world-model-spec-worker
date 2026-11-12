"""Independent original-source delivery boundary for the 500-foot reversal cases.

Review records describe what a human observed in original pixels. Diagnostic
review records can test the schema but can never produce a passing receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from lifecycle_audit import CAMERAS, audit as lifecycle_audit
from physical_motion_audit import audit as motion_audit

HERE = Path(__file__).resolve().parent
DIRECTIONS = ("reference_left", "reference_right")
FIXED = ("cell", "actor", "legal context", "traffic controls", "weather",
         "other controller settings", "camera and capture profile")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def joined_observer_distances(mapping: list[dict], trace: list[dict],
                              evidence: list[dict], rays: list[dict]) -> dict:
    """Derive eye-to-ego-body distances from original, frame-joined sources."""
    require(len(mapping) == len(trace) == len(evidence) == len(rays) == 480,
            "Original two-direction source interval incomplete")
    distances = {direction: [] for direction in DIRECTIONS}
    for index, (frame, movement, capture, viewpoints) in enumerate(
            zip(mapping, trace, evidence, rays)):
        ident, time = frame.get("native_frame"), frame.get("time_s")
        require(type(ident) is int and frame.get("video_frame") == index and
                frame.get("carla_frame") == ident and
                ident == movement.get("frame") == capture.get("original_frame") ==
                viewpoints.get("native_frame") and
                type(time) in (int, float) and math.isfinite(time) and
                all(type(value) in (int, float) and math.isfinite(value) and
                    abs(value-time) <= 1e-4 for value in
                    (movement.get("time_s"), capture.get("recording_time_s"),
                     viewpoints.get("time_s"))),
                "Original opposing-approach frame/time join differs")
        vertices = capture.get("ego", {}).get("body_vertices_m")
        require(isinstance(vertices, list) and len(vertices) >= 4 and
                all(isinstance(vertex, list) and len(vertex) >= 3 and
                    all(type(value) in (int, float) and math.isfinite(value)
                        for value in vertex[:3]) for vertex in vertices) and
                vertices == movement.get("c104538_native", {}).get("ego_body_vertices_m"),
                "Original opposing-approach body differs")
        center = [sum(vertex[axis] for vertex in vertices)/len(vertices)
                  for axis in range(3)]
        position = movement.get("position_m")
        require(isinstance(position, list) and len(position) == 3 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in position) and
                all(abs(a-b) <= 1e-4 for a, b in zip(center, position)),
                "Original opposing-approach ego center differs")
        for direction in DIRECTIONS:
            view = viewpoints.get("views", {}).get(direction, {})
            point = view.get("driver_viewpoint_xyz_m")
            require(view.get("driver_eye_point_is_assumed") is True and
                    view == movement.get("approaching_driver_views", {}).get(direction) and
                    isinstance(point, list) and len(point) == 3 and
                    all(type(value) in (int, float) and math.isfinite(value)
                        for value in point),
                    "Original approaching driver viewpoint differs: " + direction)
            distances[direction].append(math.dist(point, center)/0.3048)
    return distances


def check_pixel_review(review: dict, source_hashes: dict, mapping: list[dict],
                       case_id: str, *, diagnostic: bool,
                       observed_distances: dict | None = None) -> dict:
    require(review.get("format") == "c104538-original-pixel-review-v1" and
            review.get("case_id") == case_id and review.get("frames") == 480 and
            review.get("source_kind") == ("source_shaped_unit_test" if diagnostic else
                                          "original_native_camera_pixels") and
            review.get("reviewer") and review.get("method") and
            review.get("legal_verdict_claimed") is False,
            "Original two-direction pixel review missing or wrong source")
    require(len(mapping) == 480 and
            review.get("frame_map_sha256") == source_hashes["video_frames.jsonl"] and
            all(review.get("source_sha256", {}).get(name) == source_hashes[name]
                for name in ("trace.jsonl", "capture/evidence.jsonl",
                             "driver_eye_rays.jsonl")),
            "Pixel review frame map differs")
    views = review.get("views", {})
    require(set(views) == set(CAMERAS), "Pixel review omits a source camera")
    visible_subjects = set()
    for camera in CAMERAS:
        item = views[camera]
        require(item.get("video_sha256") == source_hashes[camera + ".mkv"] and
                item.get("reviewed_frame_ids") == list(range(480)) and
                isinstance(item.get("subjects_visible"), list) and
                item.get("limitations") is not None,
                "Original camera pixels unreviewed: " + camera)
        visible_subjects.update(item["subjects_visible"])
    require({"ego_body", "opposing_vehicle", "obstruction"} <= visible_subjects,
            "Original pixel review omits scene participants")
    observations = review.get("directions", {})
    require(set(observations) == set(DIRECTIONS),
            "Original opposing approaches not both reviewed")
    for direction in DIRECTIONS:
        item = observations[direction]
        frame = item.get("video_frame")
        distance = item.get("observer_distance_ft")
        require(type(frame) is int and 0 <= frame < 480 and
                item.get("native_frame") == mapping[frame]["native_frame"] and
                item.get("camera") in CAMERAS and
                type(distance) in (int, float) and math.isfinite(distance) and
                abs(distance - 500) <= 1 and
                all(item.get(key) in (True, False) for key in
                    ("ego_body_visible", "driver_eye_visible", "obstruction_visible")) and
                item.get("method") and item.get("limitations") is not None,
                "500-foot source pixel observation missing: " + direction)
        if observed_distances is not None:
            require(len(observed_distances.get(direction, [])) == 480 and
                    abs(item["observer_distance_ft"] -
                        observed_distances[direction][frame]) <= 1,
                    "Pixel review distance differs from original driver-eye/body sources: " +
                    direction)
    return review


def check_fixed_review(review: dict, source_hashes: dict, case_id: str,
                       *, diagnostic: bool) -> dict:
    require(review.get("format") == "c104538-original-fixed-condition-review-v1" and
            review.get("source_kind") == ("source_shaped_unit_test" if diagnostic else
                                          "original_native_capture") and
            review.get("case_id") == case_id and
            review.get("reviewer") and review.get("method") and
            review.get("source_sha256", {}).get("capture/evidence.jsonl") ==
                source_hashes["capture/evidence.jsonl"] and
            review.get("source_sha256", {}).get("road.xodr") ==
                source_hashes["road.xodr"] and
            set(review.get("observations", {})) == set(FIXED) and
            all(review["observations"][name] is not None for name in FIXED) and
            review.get("legal_verdict_claimed") is False,
            "Original fixed-condition review incomplete")
    return review


def audit(attempt: Path, saved: Path, owner_receipt: Path, case_id: str,
          candidate_id: str, construction_sha256: str, pixel_review: Path,
          fixed_review: Path, primary_video: Path, core_trace: Path,
          decode_dir: Path) -> dict:
    attempt, saved, decode_dir = (path.resolve() for path in
                                (attempt, saved, decode_dir))
    require(case_id in {HERE.name + "__" + suffix for suffix in
                        ("below_500_ft", "at_500_ft", "above_500_ft")},
            "Delivery selects another case")
    life = lifecycle_audit(attempt, owner_receipt, saved/"processing.json",
                           case_id, candidate_id, construction_sha256)
    motion = motion_audit(attempt, case_id)
    require(motion["native_motion_status"] == "met",
            "Original Native physical reversal absent")
    processing = read(saved/"processing.json")
    require(processing.get("timestamp_joins", {}).get("passed") is True and
            all(processing.get("original_source_hashes", {}).get(name) == digest
                for name, digest in motion["source_sha256"].items()),
            "Saved source/frame joins differ")
    source_hashes = {name: sha(attempt/name) for name in
        ("video_frames.jsonl", "capture/evidence.jsonl", "road.xodr",
         "trace.jsonl", "driver_eye_rays.jsonl",
         *(camera + ".mkv" for camera in CAMERAS))}
    mapping = rows(attempt/"video_frames.jsonl")
    distances = joined_observer_distances(
        mapping, rows(attempt/"trace.jsonl"),
        rows(attempt/"capture/evidence.jsonl"),
        rows(attempt/"driver_eye_rays.jsonl"))
    pixel = check_pixel_review(read(pixel_review), source_hashes, mapping,
                               case_id, diagnostic=False,
                               observed_distances=distances)
    check_fixed_review(read(fixed_review), source_hashes, case_id,
                       diagnostic=False)
    result_path = Path(processing["result"]).resolve()
    require(saved in result_path.parents and result_path.is_file() and
            processing.get("result_sha256") == sha(result_path),
            "Saved result changed")
    result = read(result_path)
    require(result.get("case_id") == case_id and
            result.get("maneuver_completed") is True and
            result.get("legal_verdict_claimed") is False,
            "Saved result does not reflect original physical reversal")
    primary_video, core_trace = primary_video.resolve(), core_trace.resolve()
    require(attempt in primary_video.parents and attempt in core_trace.parents and
            primary_video.is_file() and core_trace.is_file(),
            "Primary video or Core trace missing from original attempt")
    scenes = read(core_trace).get("scenes", [])
    require(len(scenes) == len(mapping) == 480 and
            all(scene.get("t") == round(frame["time_s"]*1000)
                for scene, frame in zip(scenes, mapping)),
            "Core trace differs from original frame map")
    from scenario_pipeline.worker_exchange.media import audit as decode
    decode_dir.mkdir(parents=True, exist_ok=True)
    decode_receipts = {}
    for camera in CAMERAS:
        path = decode_dir/(camera + ".json")
        decode(attempt/(camera + ".mkv"), 480, receipt=path,
               mapping_sha256=source_hashes["video_frames.jsonl"])
        decode_receipts[camera] = {"path": str(path), "sha256": sha(path)}
    primary_receipt = decode_dir/"primary.json"
    decoded = decode(primary_video, 480, receipt=primary_receipt,
                     mapping_sha256=source_hashes["video_frames.jsonl"])
    require(all(pixel["directions"][direction]["camera"] in CAMERAS
                for direction in DIRECTIONS), "Pixel observation camera absent")
    return {"format": "worker-delivery-audit", "passed": True,
            "source_shaped_unit_test": False, "case_id": case_id,
            "attempt_path": str(attempt), "saved_path": str(saved),
            "checks": {key: True for key in
                       ("native_source", "all_participants", "time_join",
                        "full_video_decode", "actual_pixels", "physical_completion")},
            "source_result_sha256": sha(result_path),
            "source_decode_receipt_path": str(primary_receipt),
            "source_decode_receipt_sha256": sha(primary_receipt),
            "source_decode_auditor_sha256": decoded["auditor_sha256"],
            "source_camera_decode_receipts": decode_receipts,
            "pixel_review_path": str(pixel_review.resolve()),
            "pixel_review_sha256": sha(pixel_review),
            "fixed_condition_review_path": str(fixed_review.resolve()),
            "fixed_condition_review_sha256": sha(fixed_review),
            "lifecycle_capture_seal_sha256": life["capture_seal_sha256"],
            "motion_auditor_sha256": sha(HERE/"physical_motion_audit.py"),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(Path(__file__)),
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("attempt", "saved", "owner-receipt", "pixel-review",
                 "fixed-review", "primary-video", "core-trace", "decode-dir",
                 "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    receipt = audit(args.attempt, args.saved, args.owner_receipt, args.case,
                    args.candidate, args.construction_sha256,
                    args.pixel_review, args.fixed_review, args.primary_video,
                    args.core_trace, args.decode_dir)
    require(not args.output.exists(), "Retain previous independent audit")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
