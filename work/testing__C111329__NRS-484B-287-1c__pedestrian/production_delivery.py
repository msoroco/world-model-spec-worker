"""Audit one sealed original attempt and its independent pixel review.

This is a local execution gate. CPU fixtures cannot supply its review packet.
The result describes observed completion, not statutory compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from independent_cpu_delivery import inspect
from native_observation import CAMERAS


def _review(attempt: Path, reference: dict) -> dict:
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError("independent original review reference required")
    original = attempt / reference["path"]
    path = original.resolve()
    if not path.is_relative_to(attempt) or original.is_symlink() or not path.is_file():
        raise ValueError("independent original review must be inside saved attempt")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != reference.get("sha256"):
        raise ValueError("independent original review hash mismatch")
    return json.loads(path.read_text())


def audit_original(attempt_dir: Path, case_id: str, review_ref: dict) -> dict:
    attempt = Path(attempt_dir).resolve()
    measured = inspect(attempt, case_id, diagnostic=False)
    review = _review(attempt, review_ref)
    start, end = measured["crossing_frame_range"]
    expected_video_hashes = measured["encoded_camera_source_sha256"]
    if (review.get("format") != "independent-original-pedestrian-review" or
            review.get("case_id") != case_id or
            review.get("source") != "original_four_camera_video" or
            review.get("diagnostic_fixture") is not False or
            not review.get("reviewer") or not review.get("method") or
            review.get("observation_sha256") != measured["source_observation_sha256"] or
            review.get("native_seal_sha256") != measured["native_provenance"]["seal_sha256"] or
            review.get("video_sha256") != expected_video_hashes or
            review.get("site_source_sha256") != measured["source_sha256"] or
            review.get("reviewed_frame_ids") != [0, start, end, 899]):
        raise ValueError("independent physical review not bound to original source and crossing")
    if (review.get("walker_visible_in_original_views") is not True or
            review.get("crossing_completed_in_original_views") is not True or
            review.get("both_highway_banks_visible") is not True or
            review.get("both_devices_visible") is not True or
            review.get("full_original_video_reviewed") is not True or
            review.get("marking_observed") is not measured["marked_crosswalk_observed"] or
            review.get("both_devices_operating_during_crossing") is not
            measured["both_devices_operating_during_crossing"] or
            review.get("reviewed_camera_names") != list(CAMERAS)):
        raise ValueError("independent original physical visibility or case distinction missing")
    return {**measured, "physical_completion": True, "actual_pixels": True,
            "independent_review_sha256": review_ref["sha256"],
            "legal_verdict": None, "physical_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--physical-review-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.physical_review_ref.read_text())
    result = audit_original(args.attempt, args.case_id, reference)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
