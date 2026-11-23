"""Independent comparison audit for the NRS 484B.557 case matrix."""
from __future__ import annotations


FIXED_FIELDS = ("crossing_map_sha256", "crossing_authority_sha256",
                "sign_landmark_id", "nearest_rail_id", "ego_blueprint_id",
                "approach_direction", "camera_plan_sha256", "capture_fps")


def audit_pair(left: dict, right: dict, comparison: dict) -> dict:
    """Reject missing saved measurements and unintended scene changes.

    The requested comparison variable is declared by the case plan. This audit
    reports physical differences without assigning compliance or due-care labels.
    """
    ids = comparison.get("case_ids")
    if not isinstance(ids, list) or len(ids) != 2 or [left.get("case_id"), right.get("case_id")] != ids:
        raise ValueError("comparison case identity differs")
    for side in (left, right):
        if side.get("source_kind") != "original_native_saved":
            raise ValueError("comparison requires original saved source")
        if side.get("measurement_status") != "measured":
            raise ValueError("comparison requires measured result")
        if side.get("capture_fps") != 20:
            raise ValueError("comparison requires 20 Hz capture")
        if side.get("source_sha256") is None:
            raise ValueError("comparison source hash missing")
    for field in FIXED_FIELDS:
        if left.get(field) is None or right.get(field) is None or left[field] != right[field]:
            raise ValueError(f"fixed comparison field differs: {field}")
    variable = comparison.get("variable")
    if variable not in {"stop_position_ft", "cessation", "crossing_conflict"}:
        raise ValueError("unsupported comparison variable")
    measured_field = {"stop_position_ft": "first_stop_body_to_nearest_rail_min_ft",
                      "cessation": "complete_stop_observed",
                      "crossing_conflict": "crossing_conflict_observed"}[variable]
    if measured_field not in left or measured_field not in right:
        raise ValueError("declared comparison measurement missing")
    if left[measured_field] == right[measured_field]:
        raise ValueError("declared comparison lacks measured contrast")
    return {"comparison_id": comparison.get("comparison_id"), "status": "measured_contrast",
            "variable": variable, "left": left[measured_field], "right": right[measured_field],
            "legal_judgment": "unresolved"}
