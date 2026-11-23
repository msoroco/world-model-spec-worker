"""Independent saved-source audit for the four through-highway cases.

This checks a sealed original-frame packet. Physical visibility and legal review
remain local acceptance tasks; fixture bytes do not prove either one.
"""

import hashlib
from pathlib import Path

CAMERAS = ("front", "rear", "left", "right")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def check_file(ref, reason):
    path = Path(ref.get("path", ""))
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref.get("sha256"), reason)


def audit_saved(source, measured):
    require(source.get("case_id") == measured.get("case_id"), "exact case binding mismatch")
    require(source.get("map_sha256") == measured.get("map_sha256") and source.get("intersection_id") == measured.get("intersection_id"), "map or intersection source mismatch")
    check_file(source.get("native_result", {}), "sealed Native result mismatch")
    for name in ("municipal_jurisdiction", "through_highway_designation", "entrance_control", "antecedent_review"):
        check_file(source.get(name, {}), f"{name} source seal mismatch")
    frame_map = source.get("frame_map")
    count = measured.get("original_frame_count")
    require(isinstance(count, int) and count >= 400 and isinstance(frame_map, list) and len(frame_map) == count, "complete original frame map missing")
    for i, row in enumerate(frame_map):
        require(row.get("frame_index") == i and row.get("native_frame") is not None
                and isinstance(row.get("time_s"), (int, float)) and abs(row["time_s"] - i / 20) <= 0.002,
                "original frame/time join failed")
    samples = measured.get("original_samples")
    require(isinstance(samples, list) and len(samples) == count, "measured original history missing")
    for i, row in enumerate(samples):
        require(row.get("frame_index") == i and abs(row.get("time_s", -1) - frame_map[i]["time_s"]) <= 0.002,
                "measurement frame/time join failed")
        require(all(row.get(role, {}).get("center_xy") is not None for role in ("through", "entering")),
                "both actor histories missing")
    cameras = source.get("cameras", {})
    require(set(cameras) == set(CAMERAS), "four camera sources missing")
    for name in CAMERAS:
        camera = cameras[name]
        check_file(camera, f"{name} camera seal mismatch")
        require(camera.get("decoded_frames") == count and camera.get("original_frame_first") == 0
                and camera.get("original_frame_last") == count - 1, f"{name} full decode/frame join missing")
    require(source.get("physical_completion") is True, "physical completion receipt missing")
    return {"format": "worker-through-highway-saved-audit", "case_id": source["case_id"],
            "original_frame_count": count, "source_seals_checked": True,
            "physical_visibility": "requires_review", "legal_status": "unresolved"}


def audit_comparison(left_source, left_measured, right_source, right_measured):
    left = audit_saved(left_source, left_measured)
    right = audit_saved(right_source, right_measured)
    require(left_measured.get("entering_maneuver") == right_measured.get("entering_maneuver")
            and left_measured.get("intersection_id") == right_measured.get("intersection_id")
            and left_measured.get("map_sha256") == right_measured.get("map_sha256"),
            "comparison fixed conditions changed")
    require(left_measured.get("through_request") == "yield_request"
            and right_measured.get("through_request") == "continue_request", "comparison requested difference missing")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "original_frame_counts": [left["original_frame_count"], right["original_frame_count"]],
            "legal_status": "unresolved"}
