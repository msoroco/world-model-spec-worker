"""Independent C110454 delivery boundary for an original sealed Native attempt.

Diagnostic mode checks source shape only. It never creates an accepting receipt.
A reviewer must inspect original pixels and surveyed context before original mode.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = "training__C110454__NRS-484B-213-2b__motor_vehicle_driver"
ROOT = next((parent for parent in HERE.parents if (parent / "batch.json").is_file()), None)
if ROOT is None:
    raise RuntimeError("Original delivery audit needs the batch repository")
PACKAGE = ROOT / "work" / AID
sys.path.insert(0, str(PACKAGE))

from camera_lifecycle_audit import CAMERAS, audit as audit_cameras  # noqa: E402
from physical_motion_audit import EXPECTED, audit as audit_motion  # noqa: E402
from source_join_audit import read, require, rows, sha  # noqa: E402
TARGET = {"rail_reference": "railroad_crossing", "rail_contrast": "railroad_crossing",
          "oneway_absent": "roadway", "oneway_present": "roadway",
          "traversal_reference": "intersection", "traversal_contrast": "intersection"}
ZONE_KIND = {suffix: ("railroad_crossing" if suffix.startswith("rail_") else "intersection")
             for suffix in EXPECTED}
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def within(root: Path, path: Path) -> Path:
    root, path = root.resolve(), path.resolve()
    require(root in path.parents, "Delivery source escapes selected attempt")
    return path


def selected_entry(case_id: str, candidate_id: str, construction_sha256: str) -> dict:
    manifest = read(PACKAGE / "execution-manifest.json")
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    require(entry is not None and case_id.startswith(AID + "__"), "Unselected delivery case")
    candidate = entry if candidate_id == "primary" else next(
        (row for row in entry["candidates"] if row["id"] == candidate_id), None)
    require(candidate is not None and candidate["construction_sha256"] == construction_sha256 and
            sha(PACKAGE / candidate["construction"]) == construction_sha256,
            "Delivery construction differs from selected manifest")
    return entry


def check_pixel_review(review: dict, case_id: str, source_hashes: dict,
                       decoded: dict, *, diagnostic: bool) -> dict:
    """Bind human frame review to independently decoded four-camera RGB bytes."""
    suffix = case_id.removeprefix(AID + "__")
    require(suffix in EXPECTED and review.get("format") == "c110454-original-pixel-review-v1" and
            review.get("case_id") == case_id and review.get("frames") == 480 and
            review.get("source_kind") == ("source_shaped_unit_test" if diagnostic else
                                          "original_native_camera_pixels") and
            review.get("reviewer") and review.get("method") and
            review.get("frame_map_sha256") == source_hashes["video_frames.jsonl"] and
            review.get("legal_verdict_claimed") is False,
            "Original pixel review missing or wrong source")
    views = review.get("views", {})
    require(set(views) == set(CAMERAS), "Pixel review omits a source camera")
    visible = set()
    for camera in CAMERAS:
        item = views[camera]
        digest = source_hashes[camera + ".mkv"]
        decoded_item = decoded.get(digest)
        require(item.get("video_sha256") == digest and
                item.get("reviewed_frame_ids") == list(range(480)) and
                isinstance(item.get("subjects_visible"), list) and
                item.get("limitations") is not None and
                decoded_item is not None and decoded_item.get("frames") == 480 and
                item.get("rgb_sequence_sha256") == decoded_item.get("rgb_sequence_sha256"),
                "Original camera pixels unreviewed or decode changed: " + camera)
        visible.update(item["subjects_visible"])
    if diagnostic:
        require(not visible, "Diagnostic pixels cannot claim visible participants")
    else:
        require({"ego_body", "roadway", TARGET[suffix]} <= visible,
                "Original pixel review omits ego or statutory scene")
    return review


def check_context_review(review: dict, attempt: Path, case_id: str,
                         *, diagnostic: bool) -> dict:
    suffix = case_id.removeprefix(AID + "__")
    context_name = "context.json" if suffix.startswith("traversal_") else "statutory_context.json"
    survey = read(attempt / "road_geometry.json")
    require(review.get("format") == "c110454-original-road-context-review-v1" and
            review.get("case_id") == case_id and review.get("source_kind") ==
            ("source_shaped_unit_test" if diagnostic else "original_native_map_and_scene") and
            review.get("reviewer") and review.get("method") and
            review.get("road_geometry_sha256") == sha(attempt / "road_geometry.json") and
            review.get("road_xodr_sha256") == sha(attempt / "road.xodr") and
            review.get("statutory_or_traversal_context_sha256") == sha(attempt / context_name) and
            review.get("native_map_sha256") == survey.get("native_map_sha256") and
            review.get("legal_verdict_claimed") is False,
            "Original road/context review missing or source changed")
    if diagnostic:
        require(review.get("designation_confirmed") is False,
                "Diagnostic context cannot confirm physical designation")
    else:
        require(review.get("designation_confirmed") is True and
                review.get("zone_kind") == ZONE_KIND[suffix] and
                review.get("observations") and review.get("limitations") is not None,
                "Original Native designation or scene review incomplete")
        if suffix.startswith("traversal_"):
            require(review.get("two_way_native_readback") is True,
                    "Original two-way intersection designation unconfirmed")
        else:
            require(review.get("one_way_native_readback") is (suffix == "oneway_present") and
                    review.get("railroad_crossing_native_readback") is suffix.startswith("rail_") and
                    review.get("one_way_native_readback") is survey.get("one_way_native_readback") and
                    review.get("railroad_crossing_native_readback") is
                    survey.get("railroad_crossing_native_readback"),
                    "Original roadway or railroad designation differs")
    return review


def check_core_trace(core_trace: Path, frame_map: Path) -> int:
    mapping = rows(frame_map)
    scenes = read(core_trace).get("scenes", [])
    require(len(mapping) == len(scenes) == 480 and
            all(frame.get("video_frame") == i and
                scene.get("t") == round(frame["time_s"] * 1000)
                for i, (frame, scene) in enumerate(zip(mapping, scenes))),
            "Original frame/Core timestamp join differs")
    return len(scenes)


def audit(attempt: Path, processing: Path, case_id: str, candidate_id: str,
          construction_sha256: str, *, pixel_review: Path | None = None,
          context_review: Path | None = None, primary_video: Path | None = None,
          core_trace: Path | None = None, decode_receipt: Path | None = None,
          job_id: str | None = None, attempt_number: int | None = None,
          recording_id: str | None = None, diagnostic: bool = False) -> dict:
    attempt, processing = Path(attempt).resolve(), Path(processing).resolve()
    selected_entry(case_id, candidate_id, construction_sha256)
    decoded = {} if not diagnostic else None
    cameras = audit_cameras(attempt, processing, case_id, candidate_id,
                            construction_sha256, diagnostic=diagnostic, decoded=decoded)
    motion = audit_motion(attempt, processing, case_id, candidate_id,
                          construction_sha256, diagnostic=diagnostic)
    require(motion["source_shaped_motion_status"] == "matched",
            "Selected physical-motion relation absent")
    if diagnostic:
        return {"format": "worker-delivery-audit", "passed": False,
                "case_id": case_id, "candidate_id": candidate_id,
                "source_shaped_unit_test": True,
                "checks": {name: False for name in CHECKS},
                "camera_source_shape_passed": cameras["camera_source_shape_passed"],
                "physical_source_shape_passed": True,
                "physical_or_legal_acceptance_claimed": False}
    require(cameras["owner_release_verified"] is True and
            motion["native_motion_status"] == "met" and
            pixel_review is not None and context_review is not None and
            primary_video is not None and core_trace is not None and decode_receipt is not None and
            job_id and recording_id and type(attempt_number) is int and attempt_number >= 1,
            "Original delivery audit inputs or Native closure missing")
    local_operations = ROOT / "state/operations/worker_exchange/full-train-delivery"
    require(HERE == local_operations and
            local_operations in Path(decode_receipt).resolve().parents,
            "Original delivery auditor and decode receipt must be imported into local operations")
    saved = read(processing)
    require(saved.get("timestamp_joins", {}).get("passed") is True,
            "Saved original timestamp joins missing")
    result_path = within(attempt, attempt / "result.json")
    require(result_path.is_file() and saved.get("result_sha256") == sha(result_path),
            "Sealed Native result differs from saved processing")
    result = read(result_path)
    require(result.get("case_id") == case_id and result.get("provenance_kind") == "native" and
            result.get("maneuver_completed") is True and result.get("accepted") is False and
            result.get("legal_verdict_claimed") is False and
            any(item.get("matched") is True for item in result.get("target_checks", [])),
            "Original Native result does not show completed selected maneuver")
    source_hashes = {name: sha(attempt / name) for name in
                     ("video_frames.jsonl", *(camera + ".mkv" for camera in CAMERAS))}
    require(all(saved.get("original_source_hashes", {}).get(name) == digest
                for name, digest in source_hashes.items()),
            "Saved original camera/frame sources differ")
    pixel_review = Path(pixel_review).resolve()
    context_review = Path(context_review).resolve()
    check_pixel_review(read(pixel_review), case_id, source_hashes, decoded,
                       diagnostic=False)
    check_context_review(read(context_review), attempt, case_id, diagnostic=False)
    primary_video = within(attempt, Path(primary_video))
    core_trace = within(attempt, Path(core_trace))
    require(primary_video.is_file() and core_trace.is_file(),
            "Original primary video or Core trace missing")
    frames = check_core_trace(core_trace, attempt / "video_frames.jsonl")
    decode_receipt = Path(decode_receipt).resolve()
    require(not decode_receipt.exists(), "Retain previous source decode receipt")
    from scenario_pipeline.worker_exchange.media import audit as decode
    decoded_primary = decode(primary_video, frames, receipt=decode_receipt,
                             mapping_sha256=source_hashes["video_frames.jsonl"])
    return {"format": "worker-delivery-audit", "passed": True,
            "case_id": case_id, "candidate_id": candidate_id,
            "job_id": job_id, "attempt": attempt_number, "recording_id": recording_id,
            "checks": {name: True for name in CHECKS},
            "frames": frames, "video": str(primary_video.relative_to(attempt)),
            "video_sha256": sha(primary_video),
            "trace": str(core_trace.relative_to(attempt)), "trace_sha256": sha(core_trace),
            "source_result_sha256": sha(result_path),
            "source_decode_receipt_path": str(decode_receipt),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "source_decode_auditor_sha256": decoded_primary["auditor_sha256"],
            "pixel_review_sha256": sha(pixel_review),
            "context_review_sha256": sha(context_review),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(Path(__file__)),
            "physical_motion_auditor_sha256": sha(Path(audit_motion.__code__.co_filename)),
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("attempt", "processing", "pixel-review", "context-review",
                 "primary-video", "core-trace", "decode-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=name in ("attempt", "processing", "output"))
    for name in ("case", "candidate", "construction-sha256", "job-id", "recording-id"):
        parser.add_argument("--" + name, required=name in ("case", "candidate", "construction-sha256"))
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    receipt = audit(args.attempt, args.processing, args.case, args.candidate,
                    args.construction_sha256, pixel_review=args.pixel_review,
                    context_review=args.context_review, primary_video=args.primary_video,
                    core_trace=args.core_trace, decode_receipt=args.decode_receipt,
                    job_id=args.job_id, attempt_number=args.attempt_number,
                    recording_id=args.recording_id, diagnostic=args.diagnostic)
    require(not args.output.exists(), "Retain previous independent audit")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
