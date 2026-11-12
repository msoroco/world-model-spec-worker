"""Adapt source-joined C104538 motion into a physical outcome result.

Diagnostic shapes remain unverified. A complete Native result requires the
independent motion and lifecycle audits over retained original sources.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lifecycle_audit import audit as audit_lifecycle
from physical_motion_audit import SOURCES, audit as audit_motion


def outcome(attempt: Path, case_id: str, *, diagnostic: bool = False,
            owner_receipt: Path | None = None, processing: Path | None = None,
            candidate_id: str = "primary", construction_sha256: str | None = None) -> dict:
    motion = audit_motion(attempt, case_id, diagnostic=diagnostic)
    status = motion["native_motion_status"]
    lifecycle = None
    if not diagnostic and not motion["missing_sources"]:
        if owner_receipt is None or processing is None or not construction_sha256:
            raise ValueError("Original Native lifecycle inputs required")
        lifecycle = audit_lifecycle(attempt, owner_receipt, processing,
                                    case_id, candidate_id, construction_sha256)
        if not lifecycle["passed"] or not lifecycle["saved_processing_after_owner_release"]:
            raise ValueError("Original Native ownership closure required")
    if diagnostic:
        status = "unverified"
    result = {
        "format": "c104538-physical-outcome-v1",
        "case_id": case_id,
        "candidate_id": candidate_id,
        "provenance_kind": "synthetic_local_diagnostic" if diagnostic else
                           ("native" if lifecycle is not None else "missing"),
        "diagnostic_fixture": diagnostic,
        "maneuver_completed": status == "met" and lifecycle is not None,
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "480-frame original Native source join of body path, heading and signed velocity"
                      if lifecycle is not None else "diagnostic source-shape or missing-source assessment",
            "sources": list(motion["source_sha256"].keys()) or list(SOURCES),
            "measured": motion["measured"] if lifecycle is not None else None,
            "diagnostic_engineering_status": motion["source_shaped_motion_status"] if diagnostic else None,
        }},
        "realized_observables": {"motion": motion["measured"],
                                 "lifecycle_capture_seal_sha256": lifecycle["capture_seal_sha256"]}
                                if status == "met" and lifecycle is not None else None,
        "source_sha256": motion["source_sha256"],
        "missing_sources": motion["missing_sources"],
        "lifecycle_audit": lifecycle,
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
        "two_direction_original_pixel_visibility_proven": False,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--owner-receipt", type=Path)
    parser.add_argument("--processing", type=Path)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--construction-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = outcome(args.attempt, args.case, diagnostic=args.diagnostic,
                     owner_receipt=args.owner_receipt, processing=args.processing,
                     candidate_id=args.candidate, construction_sha256=args.construction_sha256)
    if args.output:
        if args.output.exists():
            raise ValueError("Retain previous physical outcome result")
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
