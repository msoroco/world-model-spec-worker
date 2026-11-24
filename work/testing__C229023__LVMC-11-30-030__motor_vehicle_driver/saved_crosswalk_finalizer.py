"""Saved-only crosswalk measurement from original actor and camera sources.

The measured sequence is an engineering observation, not a legal verdict or
physical acceptance of crossing purpose, sight lines, or right of way.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID, measure
from saved_video_audit import audit as audit_video


def finalize(*, directory: str | Path, case_id: str, fixture_mode: bool = False) -> dict:
    prefix = ASSIGNMENT_ID + "__"
    if not case_id.startswith(prefix) or case_id[len(prefix):] not in CASES:
        raise ValueError("exact crosswalk case required")
    root = Path(directory)
    if not root.is_dir() or (root / "crosswalk-measurement.json").exists():
        raise ValueError("fresh saved attempt with no prior finalization required")
    measured = measure(case_id=case_id, context_path=root / "context.json",
                       trace_path=root / "trace.jsonl", receipt_path=root / "receipt.json",
                       fixture_mode=fixture_mode)
    media = audit_video(directory=root, case_id=case_id, fixture_mode=fixture_mode)
    if measured["frame_count"] != media["videos"]["overview"]["frames"]:
        raise ValueError("original actor and decoded camera frame counts differ")
    crossing, behavior, purpose = CASES[case_id[len(prefix):]]
    if (measured["crosswalk_kind"], measured["stopped_vehicle_purpose_claim"]) != (crossing, purpose):
        raise ValueError("original crossing kind or purpose differs from exact case")
    observed = {
        "rear_approach_sampled": bool(measured["rear_approach_frames"]),
        "lead_stop_sampled": bool(measured["lead_stopped_frames"]),
        "pedestrian_in_polygon_sampled": bool(measured["pedestrian_crosswalk_frames"]),
        "ego_full_pass_sampled": bool(measured["ego_ahead_frames"]),
    }
    checks = [
        {"target": name, "requested": request, "measured": observed[name],
         "matched": observed[name] == request, "physical_cause_confirmed": False}
        for name, request in (
            ("rear_approach_sampled", True), ("lead_stop_sampled", True),
            ("pedestrian_in_polygon_sampled", True),
            ("ego_full_pass_sampled", behavior == "pass"),
        )
    ]
    report = {
        "format": "crosswalk-saved-measurement",
        "assignment_id": ASSIGNMENT_ID, "case_id": case_id,
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")},
        "media": media, "observed": observed, "target_checks": checks,
        "measured_values": measured, "physical_acceptance": "unverified",
        "legal_judgment": "unresolved", "legal_verdict_claimed": False,
        "diagnostic_fixture": fixture_mode,
    }
    (root / "crosswalk-measurement.json").write_text(
        json.dumps(report, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report
