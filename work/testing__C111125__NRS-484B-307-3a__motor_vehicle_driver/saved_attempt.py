"""Saved-only dual-green measurement from original packets, with no legal verdict."""
from __future__ import annotations

import json
from pathlib import Path

from dual_green import measure_original, read_source, require
from camera_audit import audit_cameras


def measure_saved(site, source_root, attempt_dir, case_id):
    attempt = Path(attempt_dir)
    receipt = json.loads((attempt / "native-attempt.json").read_text(encoding="utf-8"))
    require(receipt["case_id"] == case_id, "attempt case mismatch")
    require(receipt["sample_hz"] == 20 and receipt["physical_acceptance_claimed"] is False,
            "attempt provenance invalid")
    require(receipt["permission_verdict"] is None and receipt["right_of_way_verdict"] is None,
            "unsupported attempt verdict")
    event_ref = receipt["event_source"]
    events = json.loads(read_source(attempt, event_ref).read_text(encoding="utf-8"))
    require(len(events) == receipt["frame_count"] >= 3, "incomplete saved attempt")
    require(events[0]["frame"] == receipt["first_frame"] and events[-1]["frame"] == receipt["last_frame"],
            "saved frame bounds mismatch")
    previous_time = None
    previous_frame = None
    for row in events:
        lamp_ref = {"path": row["aspect_observation_source"],
                    "sha256": row["aspect_observation_sha256"]}
        packet = json.loads(read_source(source_root, lamp_ref).read_text(encoding="utf-8"))
        require(packet["frame"] == row["frame"] and packet["official_head_id"] == row["official_head_id"]
                and packet["facing_approach_id"] == row["facing_approach_id"]
                and packet["lit_aspects"] == row["lit_aspects"], "lamp source does not match saved frame")
        for user in row["other_users"]:
            lawful_ref = {"path": user["lawful_use_source"], "sha256": user["lawful_use_sha256"]}
            lawful = json.loads(read_source(source_root, lawful_ref).read_text(encoding="utf-8"))
            require(lawful["frame"] == row["frame"] and str(lawful["user_id"]) == user["id"],
                    "lawful-use source does not match saved user")
        elapsed = float(row["elapsed_seconds"])
        if previous_time is not None:
            require(abs(elapsed - previous_time - 0.05) <= 1e-4, "saved 20 Hz timing gap")
            require(row["frame"] == previous_frame + 1, "saved frame gap")
        previous_time = elapsed
        previous_frame = row["frame"]
    measured = measure_original(site, source_root, event_ref, event_root=attempt)
    return {"case_id": case_id, "frame_count": receipt["frame_count"],
            "exhibition": measured["exhibition"], "records": measured["records"],
            "original_sources": measured["original_sources"],
            "permission_verdict": None, "right_of_way_verdict": None,
            "physical_acceptance_claimed": False}


def measure_delivery(site, source_root, attempt_dir, case_id):
    """Require the production 900-frame, four-camera saved source join."""
    measured = measure_saved(site, source_root, attempt_dir, case_id)
    camera_receipt = audit_cameras(attempt_dir, case_id)
    require(measured["frame_count"] == camera_receipt["frame_count"],
            "delivery camera/event frame mismatch")
    measured["camera_audit"] = camera_receipt
    return measured
