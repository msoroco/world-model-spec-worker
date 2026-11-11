"""Independent, value-free audit of C147331 controlled comparison packets."""

from __future__ import annotations


PAIRS = {
    "ordinary_lane_containment": ("within_marked_lane", "unexcused_boundary_crossing"),
    "passing_exception_context": ("unexcused_boundary_crossing", "passing_boundary_crossing"),
}

FIXED = ("map_id", "lane_geometry_sha256", "marking_inventory_sha256",
         "ego_blueprint", "camera_plan_sha256", "duration_s", "fps")


def audit_comparison(comparison_id, left, right):
    """Require source-bound differences and matching declared fixed conditions.

    Inputs are independently generated saved measurement packets. This checker
    cannot decide lawful passing; it checks the recorded context only.
    """
    if comparison_id not in PAIRS:
        raise ValueError("Unknown lane comparison")
    suffixes = PAIRS[comparison_id]
    for packet, suffix in zip((left, right), suffixes):
        if not packet.get("case_id", "").endswith("__" + suffix):
            raise ValueError("Comparison case identity mismatch")
        if not packet.get("source_sha256") or not packet.get("measurement_sha256"):
            raise ValueError("Original source or measurement hash missing")
        if not packet.get("frames"):
            raise ValueError("Original lane frame evidence missing")
        if any(field not in packet.get("fixed", {}) for field in FIXED):
            raise ValueError("Declared fixed condition missing")
    changed = [field for field in FIXED
               if left["fixed"][field] != right["fixed"][field]]
    if changed:
        raise ValueError("Fixed conditions changed: " + ", ".join(changed))
    if comparison_id == "ordinary_lane_containment":
        if any(not frame.get("full_footprint_inside") for frame in left["frames"]):
            raise ValueError("Within-lane case lacks measured containment")
        if not any(not frame.get("full_footprint_inside") for frame in right["frames"]):
            raise ValueError("Crossing case lacks measured boundary excursion")
        if left["fixed"].get("passing_participant_id") is not None or right["fixed"].get("passing_participant_id") is not None:
            raise ValueError("Ordinary containment comparison includes passing")
    else:
        if not all(any(not frame.get("full_footprint_inside") for frame in packet["frames"])
                   for packet in (left, right)):
            raise ValueError("Passing comparison lacks matched boundary excursions")
        if left["fixed"].get("passing_participant_id") is not None:
            raise ValueError("Unexcused case contains a passing participant")
        if right["fixed"].get("passing_participant_id") is None:
            raise ValueError("Passing participant evidence missing")
        if not right.get("passing_motion_source_sha256"):
            raise ValueError("Passing motion source hash missing")
    return {"comparison_id": comparison_id, "checked_cases": [left["case_id"], right["case_id"]],
            "fixed_fields": list(FIXED), "status": "software_evidence_complete",
            "legal_verdict": None}
