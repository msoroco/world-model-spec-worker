"""Independent saved-source delivery audit for an exact 253 left-turn case.

Positive CPU fixtures test verification logic only. This script does not mark
physical realization or canonical delivery accepted.
"""

import argparse
import hashlib
import json
from pathlib import Path

from saved_media_audit import CAMERAS, audit as audit_media
from saved_left_turn import ASSIGNMENT_ID


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit(*, attempt, case_id, physical_review, pixel_review, allow_diagnostic=False):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    attempt = Path(attempt)
    media = audit_media(attempt, case_id=case_id, allow_diagnostic=allow_diagnostic)
    receipt = _read(attempt / "acquisition-receipt.json")
    physical = _read(physical_review)
    pixels = _read(pixel_review)
    if physical.get("case_id") != case_id or pixels.get("case_id") != case_id:
        raise ValueError("independent review case identity mismatch")
    if physical.get("trace_sha256") != receipt["trace_sha256"] or physical.get("map_sha256") != receipt["map_sha256"]:
        raise ValueError("physical review is stale against original sources")
    if physical.get("maneuver_completed") is not True or physical.get("completion_status") != "met":
        raise ValueError("source-bound physical maneuver completion absent")
    if not physical.get("method") or not physical.get("reviewer") or not physical.get("original_frame_interval"):
        raise ValueError("physical completion method or review interval missing")
    if physical.get("participant_actor_ids") != media["participant_actor_ids"]:
        raise ValueError("physical review omits original participant identity")
    if pixels.get("frame_map_sha256") != receipt["frame_map_sha256"] or pixels.get("receipt_sha256") != _sha(attempt / "acquisition-receipt.json"):
        raise ValueError("pixel review is stale against original footage")
    if pixels.get("reviewed_frame_count") != media["frame_count"] or pixels.get("reviewed_cameras") != list(CAMERAS):
        raise ValueError("pixel review omits a frame or required camera")
    if pixels.get("visible_actor_ids") != media["participant_actor_ids"]:
        raise ValueError("pixel review omits a required actor")
    if pixels.get("intersection_boundary_visible") is not True or pixels.get("full_duration_reviewed") is not True:
        raise ValueError("actual pixel visibility review incomplete")
    if not pixels.get("method") or not pixels.get("reviewer"):
        raise ValueError("pixel review method or reviewer missing")
    return {"format": "worker-253-saved-delivery-audit", "assignment_id": ASSIGNMENT_ID,
            "case_id": case_id, "software_checks_passed": True,
            "diagnostic_fixture": receipt["diagnostic_fixture"],
            "media_decode": media,
            "review_sources": {"physical_review_sha256": _sha(physical_review),
                               "pixel_review_sha256": _sha(pixel_review)},
            "physical_acceptance": "unverified_by_worker",
            "canonical_delivery_acceptance": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--physical-review", required=True)
    parser.add_argument("--pixel-review", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(attempt=args.attempt, case_id=args.case,
                   physical_review=args.physical_review, pixel_review=args.pixel_review,
                   allow_diagnostic=args.allow_diagnostic)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
