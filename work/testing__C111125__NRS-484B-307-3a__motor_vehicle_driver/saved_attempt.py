"""Saved-only dual-green measurement from original packets, with no legal verdict."""
from __future__ import annotations

import json
from pathlib import Path

from dual_green import measure_original, read_source, require
from camera_audit import audit_cameras
from source_handoff import load_handoff


CASE_EXPECTATIONS = {
    "dual_clear": None,
    "dual_vehicle_present": ("motor_vehicle", "intersection"),
    "dual_pedestrian_present": ("pedestrian", "adjacent_crosswalk"),
    "dual_pedestrian_late": ("pedestrian", "outside"),
}


def check_case_observation(case_id, measured):
    """Check the planned contrast against original positions, without a legal verdict."""
    prefix = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
    require(case_id.startswith(prefix), "wrong exact dual-green assignment")
    suffix = case_id[len(prefix):]
    require(suffix in CASE_EXPECTATIONS, "unknown exact dual-green case")
    users = measured["exhibition"]["other_users"]
    records = measured["records"]
    require(records and any(row["frame"] == measured["exhibition"]["frame"] for row in records),
            "exhibition absent from saved records")
    expected = CASE_EXPECTATIONS[suffix]
    if expected is None:
        require(not users and all(not row["other_users"] for row in records),
                "clear case has another user")
        return {"case_suffix": suffix, "observed_difference": "clear_at_exhibition"}
    kind, region = expected
    require(len(users) == 1 and users[0]["kind"] == kind and users[0]["region"] == region,
            "other-user exhibition contrast not observed")
    require(all(len(row["other_users"]) == 1 and
                row["other_users"][0]["id"] == users[0]["id"] and
                row["other_users"][0]["kind"] == kind for row in records),
            "other-user identity or kind changed across saved frames")
    if suffix == "dual_pedestrian_late":
        pedestrian_id = users[0]["id"]
        first_frame = measured["exhibition"]["frame"]
        require(any(row["frame"] > first_frame and any(
            user["id"] == pedestrian_id and user["region"] == "adjacent_crosswalk"
            for user in row["other_users"]) for row in measured["records"]),
            "late pedestrian never entered adjacent crosswalk")
    return {"case_suffix": suffix, "observed_difference": region + "_at_exhibition"}


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
    trace = [json.loads(line) for line in read_source(attempt, receipt["trace_source"])
             .read_text(encoding="utf-8").splitlines()]
    frame_map = [json.loads(line) for line in read_source(attempt, receipt["frame_map_source"])
                 .read_text(encoding="utf-8").splitlines()]
    require(len(events) == receipt["frame_count"] >= 3, "incomplete saved attempt")
    require(len(trace) == len(events) == len(frame_map),
            "saved trace/frame map count mismatch")
    require(events[0]["frame"] == receipt["first_frame"] and events[-1]["frame"] == receipt["last_frame"],
            "saved frame bounds mismatch")
    previous_time = None
    previous_frame = None
    for index, row in enumerate(events):
        trace_row, mapped = trace[index], frame_map[index]
        require(mapped["video_frame"] == index and mapped["carla_frame"] == row["frame"] and
                trace_row["frame"] == row["frame"] and
                abs(float(mapped["time_s"]) - float(row["elapsed_seconds"])) <= 1e-4 and
                abs(float(trace_row["time_s"]) - float(row["elapsed_seconds"])) <= 1e-4,
                "saved trace/frame map identity differs")
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
    case_observation = check_case_observation(case_id, measured)
    return {"case_id": case_id, "frame_count": receipt["frame_count"],
            "exhibition": measured["exhibition"], "records": measured["records"],
            "original_sources": measured["original_sources"],
            "case_observation": case_observation,
            "permission_verdict": None, "right_of_way_verdict": None,
            "physical_acceptance_claimed": False}


def measure_delivery(site, source_root, attempt_dir, case_id):
    """Require the production 900-frame, four-camera saved source join."""
    measured = measure_saved(site, source_root, attempt_dir, case_id)
    camera_receipt = audit_cameras(attempt_dir, case_id)
    require(measured["frame_count"] == camera_receipt["frame_count"],
            "delivery camera/event frame mismatch")
    native = json.loads((Path(attempt_dir) / "native-attempt.json").read_text(encoding="utf-8"))
    handoff_ref = native.get("source_handoff")
    require(isinstance(handoff_ref, dict), "original source handoff missing")
    handoff_path = read_source(attempt_dir, handoff_ref)
    source_receipt = load_handoff(handoff_path, source_root, site, case_id,
                                  expected_frames=measured["frame_count"])
    require(source_receipt["first_frame"] == native["first_frame"] and
            source_receipt["last_frame"] == native["last_frame"],
            "original source handoff does not span saved attempt")
    measured["camera_audit"] = camera_receipt
    measured["source_handoff_sha256"] = handoff_ref["sha256"]
    return measured
