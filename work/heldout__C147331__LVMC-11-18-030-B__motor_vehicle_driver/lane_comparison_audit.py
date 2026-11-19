"""Independent, value-free audit of C147331 controlled comparison packets."""

from __future__ import annotations


PAIRS = {
    "ordinary_lane_containment": ("within_marked_lane", "unexcused_boundary_crossing"),
    "passing_exception_context": ("unexcused_boundary_crossing", "passing_boundary_crossing"),
    "turn_preparation_exception_context": ("within_marked_lane", "turn_preparation_crossing"),
}

FIXED = ("map_id", "lane_geometry_sha256", "marking_inventory_sha256",
         "ego_blueprint", "camera_plan_sha256", "duration_s", "fps")
TURN_FIXED = ("map_id", "initial_lane_geometry_sha256", "marking_inventory_sha256",
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
        fields = TURN_FIXED if comparison_id == "turn_preparation_exception_context" else FIXED
        if any(field not in packet.get("fixed", {}) for field in fields):
            raise ValueError("Declared fixed condition missing")
    fields = TURN_FIXED if comparison_id == "turn_preparation_exception_context" else FIXED
    changed = [field for field in fields
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
    elif comparison_id == "turn_preparation_exception_context":
        if any(not frame.get("full_footprint_inside") for frame in left["frames"]):
            raise ValueError("Within-lane turn control lacks measured containment")
        if not any(frame.get("boundary_crossing") for frame in right["frames"]):
            raise ValueError("Turn preparation lacks measured boundary crossing")
        control, turn = left.get("turn_preparation"), right.get("turn_preparation")
        if (not isinstance(control, dict) or control.get("requested_route") is not None
                or control.get("boundary_excursion_observed") is not False):
            raise ValueError("Within-lane turn control asserts a turn or excursion")
        route = turn.get("requested_route") if isinstance(turn, dict) else None
        if (not isinstance(route, dict) or route.get("kind") != "connected_left_turn_request"
                or turn.get("boundary_excursion_observed") is not True
                or turn.get("left_indicator_readback_observed") is not True
                or turn.get("lawful_turn_preparation_confirmed") is not False
                or left["fixed"].get("passing_participant_id") is not None
                or right["fixed"].get("passing_participant_id") is not None):
            raise ValueError("Turn request, original excursion or indicator source missing")
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
        if not right.get("measured_order_reversal"):
            raise ValueError("Measured overtaking order reversal missing")
    return {"comparison_id": comparison_id, "checked_cases": [left["case_id"], right["case_id"]],
            "fixed_fields": list(fields), "status": "software_evidence_complete",
            "legal_verdict": None}
