"""Independent source boundary for the selected NRS 484B.293 crossing.

Only an original sealed Native attempt can produce a passing delivery audit.
The motion measurement is descriptive; practicability and legality are not
decided here. Source-shaped unit tests cannot produce a passing receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lifecycle_audit import CAMERAS, audit as lifecycle_audit
from physical_outcome_audit import audit as motion_audit


HERE = Path(__file__).resolve().parent
VIEW_SUBJECTS = {
    "overview": {"pedestrian_body", "marked_crosswalk"},
    "approach": {"pedestrian_body", "marked_crosswalk_approach"},
    "reference_corner": {"pedestrian_body", "crosswalk_half_boundary"},
    "driver_reference": {"pedestrian_body", "crosswalk_route_context"},
}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(root: Path, path: Path) -> Path:
    root, path = root.resolve(), path.resolve()
    require(root in path.parents, "Delivery source escapes selected attempt")
    return path


def check_pixel_review(path: Path, attempt: Path, case_id: str, *,
                       test_shape: bool = False) -> dict:
    """Bind independent frame observations to all four original camera bytes."""
    review = read(path)
    require(review.get("format") == "c10316-source-pixel-review-v1" and
            review.get("case_id") == case_id and review.get("frames") == 240 and
            review.get("reviewer") and review.get("method") and
            review.get("source_kind") == ("source_shaped_unit_test" if test_shape
                                          else "original_native_camera_pixels") and
            review.get("legal_verdict_claimed") is False,
            "Original crosswalk pixel review missing or wrong source")
    views = review.get("views", {})
    require(set(views) == set(CAMERAS), "Crosswalk pixel review omits a camera")
    for camera in CAMERAS:
        item = views[camera]
        require(item.get("video_sha256") == sha(attempt / (camera + ".mkv")) and
                VIEW_SUBJECTS[camera] <= set(item.get("subjects_visible", [])) and
                type(item.get("reviewed_crosswalk_frames")) is int and
                item["reviewed_crosswalk_frames"] >= 60 and
                item.get("limitations") is not None,
                "Original crosswalk pixels unreviewed: " + camera)
    return review


def check_crossing_review(path: Path, attempt: Path, case_id: str, *,
                          test_shape: bool = False) -> dict:
    """Require source-backed designation and route facts without legal judgment."""
    review = read(path)
    context = read(attempt / "crosswalk-context.json")
    construction = read(attempt / "native-construction-context.json")
    require(review.get("format") == "c10316-crossing-context-review-v1" and
            review.get("case_id") == case_id and review.get("reviewer") and
            review.get("method") and
            review.get("source_kind") == ("source_shaped_unit_test" if test_shape
                                          else "original_native_map_and_scene") and
            review.get("crosswalk_context_sha256") ==
                sha(attempt / "crosswalk-context.json") and
            review.get("native_construction_sha256") ==
                sha(attempt / "native-construction-context.json") and
            review.get("native_map_sha256") == context.get("native_map_sha256") ==
                construction.get("native_map_sha256") and
            review.get("marked_highway_crosswalk_confirmed") is True and
            review.get("alley_route_connection_confirmed") is True and
            review.get("practicability_judgment") == "unverified" and
            review.get("legal_verdict_claimed") is False,
            "Marked-highway crosswalk or route context lacks original review")
    facts = review.get("facts", {})
    require(set(facts) == {"signals", "passage_space", "obstacles",
                           "other_pedestrians"},
            "Practicability context inventory incomplete")
    for name, item in facts.items():
        require(item.get("observation") is not None and
                item.get("source_path") and item.get("source_sha256"),
                "Practicability fact lacks source: " + name)
        source = within(attempt, attempt / item["source_path"])
        require(source.is_file() and sha(source) == item["source_sha256"],
                "Practicability source changed: " + name)
    return review


def audit(attempt: Path, saved: Path, owner_receipt: Path, case_id: str,
          construction_sha256: str, pixel_review: Path, crossing_review: Path,
          primary_video: Path, core_trace: Path, decode_dir: Path, *,
          test_shape: bool = False) -> dict:
    attempt, saved, decode_dir = (path.resolve() for path in
                                (attempt, saved, decode_dir))
    require(case_id in {HERE.name + "__reference", HERE.name + "__contrast"},
            "Delivery selects another case")
    life = lifecycle_audit(attempt, owner_receipt, saved / "processing.json",
                           case_id, construction_sha256, test_shape=test_shape)
    motion = motion_audit(attempt, case_id, test_shape=test_shape)
    require((motion.get("source_shaped_motion_status") == "met" if test_shape
             else motion.get("native_motion_status") == "met"),
            "Original Native crosswalk motion not established")
    processing = read(saved / "processing.json")
    require(processing.get("missing_evidence") is False and
            processing.get("timestamp_joins", {}).get("passed") is True,
            "Saved crossing lacks original source joins")
    source_hashes = processing["original_source_hashes"]
    require(all(source_hashes.get(name) == digest for name, digest in
                motion["source_sha256"].items()),
            "Motion and saved processing source hashes differ")
    result_path = Path(processing["result"]).resolve()
    result = read(result_path)
    expected = "right" if case_id.endswith("__reference") else "left"
    require(result.get("case_id") == case_id and
            result.get("measured_values", {}).get("observed_crosswalk_half") == expected and
            result.get("legal_verdict_claimed") is False and
            result.get("accepted") is False and
            (result.get("maneuver_completed") is False if test_shape else
             result.get("maneuver_completed") is True),
            "Saved crossing result does not match independent Native motion")
    pixel = check_pixel_review(pixel_review, attempt, case_id,
                               test_shape=test_shape)
    context = check_crossing_review(crossing_review, attempt, case_id,
                                    test_shape=test_shape)
    primary_video = within(attempt, primary_video)
    core_trace = within(attempt, core_trace)
    scenes = read(core_trace).get("scenes", [])
    mapping = [json.loads(row) for row in
               (attempt / "video_frames.jsonl").read_text().splitlines() if row]
    require(len(scenes) == len(mapping) == 240 and
            all(scene.get("t") == round(frame["time_s"] * 1000)
                for scene, frame in zip(scenes, mapping)),
            "Core trace differs from original frame map")
    from scenario_pipeline.worker_exchange.media import audit as decode
    mapping_sha = sha(attempt / "video_frames.jsonl")
    decode_dir.mkdir(parents=True, exist_ok=True)
    for camera in CAMERAS:
        decode(attempt / (camera + ".mkv"), 240,
               receipt=decode_dir / (camera + ".json"),
               mapping_sha256=mapping_sha)
    primary_receipt = decode_dir / "primary.json"
    decoded = decode(primary_video, 240, receipt=primary_receipt,
                     mapping_sha256=mapping_sha)
    return {"format": "worker-delivery-audit", "passed": not test_shape,
            "source_shaped_unit_test": test_shape, "case_id": case_id,
            "frames": 240, "checks": {key: True for key in
                ("native_source", "all_participants", "time_join",
                 "full_video_decode", "actual_pixels", "physical_completion")},
            "attempt_path": str(attempt), "saved_path": str(saved),
            "source_result_sha256": sha(result_path),
            "motion_status": motion["native_motion_status"],
            "motion_audit_sha256": sha(HERE / "physical_outcome_audit.py"),
            "lifecycle_capture_seal_sha256": life["capture_seal_sha256"],
            "owner_receipt_path": str(owner_receipt.resolve()),
            "owner_receipt_sha256": sha(owner_receipt),
            "video": primary_video.relative_to(attempt).as_posix(),
            "video_sha256": sha(primary_video),
            "trace": core_trace.relative_to(attempt).as_posix(),
            "trace_sha256": sha(core_trace),
            "source_decode_receipt_path": str(primary_receipt),
            "source_decode_receipt_sha256": sha(primary_receipt),
            "source_decode_auditor_sha256": decoded["auditor_sha256"],
            "source_camera_decode_receipts": {camera: {
                "path": str(decode_dir / (camera + ".json")),
                "sha256": sha(decode_dir / (camera + ".json"))}
                for camera in CAMERAS},
            "pixel_review_path": str(pixel_review.resolve()),
            "pixel_review_sha256": sha(pixel_review),
            "crossing_review_path": str(crossing_review.resolve()),
            "crossing_review_sha256": sha(crossing_review),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(Path(__file__)),
            "legal_verdict_claimed": False,
            "practicability_judgment": context["practicability_judgment"],
            "pixel_reviewer": pixel["reviewer"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("attempt", "saved", "owner-receipt", "pixel-review",
                 "crossing-review", "primary-video", "core-trace", "decode-dir",
                 "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    receipt = audit(args.attempt, args.saved, args.owner_receipt, args.case,
                    args.construction_sha256, args.pixel_review,
                    args.crossing_review, args.primary_video, args.core_trace,
                    args.decode_dir)
    require(not args.output.exists(), "Retain previous independent audit")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
