"""Three-branch crosswalk fixture evaluator with explicit provenance boundaries.

The source-shaped mode exercises the measurement algorithm only. A production
result requires the independent original-source audit and its sealed Native
capture before reporting a completed maneuver.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_outcome_audit import audit, classify, read, rows, sha


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def evaluate(attempt: Path, case_id: str, *, test_shape: bool = False,
             expected_half: str | None = None) -> dict:
    attempt = attempt.resolve()
    selected_half = "right" if case_id.endswith("__reference") else "left"
    require(case_id.endswith(("__reference", "__contrast")),
            "Unknown selected crosswalk case")
    if expected_half is not None:
        require(test_shape and expected_half in ("right", "left"),
                "Half override is reserved for diagnostic negative fixtures")
    outcome = audit(attempt, case_id, test_shape=test_shape)
    source_hashes = outcome["source_sha256"]
    missing = outcome["missing_sources"]
    if missing:
        measured = None
        diagnostic_status = "unverified"
        native_status = "unverified"
    elif expected_half is not None and expected_half != selected_half:
        samples = rows(attempt / "native_samples.jsonl")
        mapping = rows(attempt / "video_frames.jsonl")
        measured = classify(samples, mapping, read(attempt / "crosswalk-context.json"),
                            expected_half)
        diagnostic_status = measured["status"]
        native_status = "unverified"
    else:
        measured = outcome["measured"]
        diagnostic_status = outcome.get("source_shaped_motion_status", "unverified")
        native_status = outcome["native_motion_status"]
    if test_shape:
        status = "unverified"
        provenance = "source_shaped_unit_test"
    else:
        status = native_status
        provenance = "native" if status != "unverified" else "unverified"
    return {
        "format": "c10316-physical-fixture-audit-v1",
        "case_id": case_id,
        "provenance_kind": provenance,
        "diagnostic_fixture": test_shape,
        "physical_checks": {
            "maneuver": {
                "status": status,
                "maneuver_completed": status == "met" and not test_shape,
                "method": "independent_240_frame_crosswalk_footprint_audit",
                "sources": source_hashes,
                "missing_sources": missing,
                "expected_half": expected_half or selected_half,
                "source_shaped_status": diagnostic_status if test_shape else None,
                "measurement": measured,
            }
        },
        "realized_observables": measured if not test_shape and status == "met" else None,
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.attempt, args.case), indent=2))
