"""Independent saved-source delivery audit for one exact C111706 U-turn.

Diagnostic mode proves software joins only. Original mode requires Native
closure, complete camera decode and observed physical completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import source

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, processing_path, case_id, *, pixel_review_path, diagnostic=False):
    attempt = Path(attempt).resolve()
    processing_path = Path(processing_path).resolve()
    index, site, native, measured, paths, detected_diagnostic = source(attempt)
    if index["case_id"] != case_id or detected_diagnostic != diagnostic:
        raise ValueError("exact case or source provenance differs")
    processing = read(processing_path)
    if (processing.get("format") != "worker-saved-processing" or
            processing.get("passed") is not True or
            processing.get("recorded_only") is not True or
            processing.get("case_id") != case_id or
            processing.get("originals_preserved") is not True):
        raise ValueError("saved-only processing receipt missing or failed")
    for rel, digest in processing.get("original_source_hashes", {}).items():
        if not (attempt / rel).is_file() or sha(attempt / rel) != digest:
            raise ValueError("saved processing original source changed: " + rel)
    result_path = Path(processing["result"])
    if not result_path.is_file() or sha(result_path) != processing.get("result_sha256"):
        raise ValueError("saved result missing or changed")
    result = read(result_path)
    if result.get("case_id") != case_id or result.get("diagnostic_fixture") != diagnostic:
        raise ValueError("saved result identity or provenance differs")
    trace = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    frames = native["frames"]
    if len(frames) != (9 if diagnostic else 900) or len(trace) != len(frames) or len(mapping) != len(frames):
        raise ValueError("original source frame count incomplete")
    for number, (frame, motion, video) in enumerate(zip(frames, trace, mapping)):
        if (motion.get("frame") != frame["frame"] or
                abs(motion.get("time_s", float("inf")) - frame["time_s"]) > 1e-6):
            raise ValueError("original Native/trace time join differs")
        if (video.get("video_frame") != number or
                video.get("carla_frame") != frame["frame"] or
                abs(video.get("time_s", float("inf")) - frame["time_s"]) > 1e-6):
            raise ValueError("original Native/video time join differs")
        if frame["ego"]["id"] == frame["other_vehicle"]["id"]:
            raise ValueError("original participant identities collide")
    if not diagnostic:
        seal = read(attempt / "capture-seal.json")
        if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
                seal.get("restoration", {}).get("restored") is not True or
                seal.get("diagnostic_fixture") is True):
            raise ValueError("Native capture closure incomplete")
        for rel, digest in seal.get("sources", {}).items():
            if not (attempt / rel).is_file() or sha(attempt / rel) != digest:
                raise ValueError("Native sealed original missing or changed: " + rel)
        exit_receipt = read(attempt / "native-exit.json")
        owner = read(attempt / "owner-release.json")
        if (exit_receipt.get("capture_seal_sha256") != sha(attempt / "capture-seal.json") or
                owner.get("native_exit_sha256") != sha(attempt / "native-exit.json") or
                owner.get("operator_attested") is not True):
            raise ValueError("Native exit or owner release differs")
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
            raise ValueError("observed physical U-turn completion not confirmed")
    version = processing_path.parent
    from worker_exchange.media import verify_receipt
    frame_map_hash = sha(attempt / "video_frames.jsonl")
    decodes = {}
    if not Path(pixel_review_path).is_file():
        raise ValueError("independent original pixel review absent or stale")
    review = read(pixel_review_path)
    if (review.get("format") != "c111706-independent-pixel-review-v1" or
            review.get("case_id") != case_id or
            review.get("diagnostic_fixture") != diagnostic or
            review.get("frame_map_sha256") != frame_map_hash or
            review.get("source_index_sha256") != sha(attempt / "capture/source-index.json") or
            set(review.get("views", {})) != set(VIEWS) or
            not review.get("reviewer") or not review.get("method")):
        raise ValueError("independent original pixel review absent or stale")
    for number, view in enumerate(VIEWS):
        video = attempt / (view + ".mkv")
        receipt = version / f"source-{number}.json"
        decoded = verify_receipt(video, receipt, len(frames), mapping_sha256=frame_map_hash)
        if not decoded.get("rgb_sequence_sha256"):
            raise ValueError("decoded original pixels missing: " + view)
        item = review["views"][view]
        if (item.get("video_sha256") != sha(video) or
                item.get("decode_receipt_sha256") != sha(receipt) or
                item.get("rgb_sequence_sha256") != decoded["rgb_sequence_sha256"] or
                item.get("inspected_frame_count") != len(frames) or
                item.get("visibility_status") not in (
                    ("diagnostic_only",) if diagnostic else
                    ("visible", "not_visible", "occluded", "unresolved"))):
            raise ValueError("independent original pixel review absent or stale: " + view)
        if not diagnostic and not item.get("reviewed_frames"):
            raise ValueError("independent original pixel sample review missing: " + view)
        decodes[view] = sha(receipt)
    return {"format": "c111706-independent-delivery-audit-v1", "case_id": case_id,
            "passed": True, "scope": "diagnostic software only" if diagnostic else "original Native delivery",
            "diagnostic_fixture": diagnostic,
            "checks": {"native_source": not diagnostic, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": True,
                       "physical_completion": not diagnostic},
            "source_index_sha256": sha(attempt / "capture/source-index.json"),
            "native_sha256": sha(paths["native-uturn.json"]),
            "saved_processing_sha256": sha(processing_path),
            "source_decode_receipts": decodes,
            "pixel_review_sha256": sha(pixel_review_path),
            "frame_count": len(frames), "measured_reversal_deg": measured["reversal_deg"],
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processing", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--pixel-review", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.case,
                           pixel_review_path=args.pixel_review,
                           diagnostic=args.diagnostic), indent=2))


if __name__ == "__main__":
    main()
