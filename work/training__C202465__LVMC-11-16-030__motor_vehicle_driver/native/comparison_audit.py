"""Independent source-bound CPU comparison for rail speed, sight and exceptions."""

from __future__ import annotations

from rail_sight import measure_trace

FIXED = ("road_sha256", "railway_review_sha256", "approach_review_sha256",
         "camera_plan_sha256", "ego_blueprint", "rail_vehicle_actor_ids",
         "crossing_source_ref", "flagman_source_ref", "signal_source_ref")


def audit(case_a, case_b, comparison, diagnostic_fixture=False):
    if case_a.get("case_id") == case_b.get("case_id") or not comparison.get("comparison_id"):
        raise ValueError("two distinct exact comparison cases required")
    if comparison.get("case_ids") != [case_a.get("case_id"), case_b.get("case_id")]:
        raise ValueError("comparison case identity differs")
    meta_a, meta_b = case_a.get("source_metadata", {}), case_b.get("source_metadata", {})
    for key in FIXED:
        if not meta_a.get(key) or meta_a[key] != meta_b.get(key):
            raise ValueError("fixed original source differs: " + key)
    if (meta_a.get("diagnostic_fixture") or meta_b.get("diagnostic_fixture")) and not diagnostic_fixture:
        raise ValueError("diagnostic fixture cannot certify independent comparison")
    axis = comparison.get("axis")
    if axis not in ("speed", "sight", "flagman", "signal_state", "signal_visibility"):
        raise ValueError("comparison axis missing")
    if axis != "sight" and meta_a.get("blocker_source_refs") != meta_b.get("blocker_source_refs"):
        raise ValueError("undeclared sight blocker change")
    if axis == "sight" and meta_a.get("blocker_source_refs") == meta_b.get("blocker_source_refs"):
        raise ValueError("sight comparison lacks source geometry change")
    crossing_a, crossing_b = case_a.get("crossing"), case_b.get("crossing")
    if not crossing_a or not crossing_b or crossing_a != crossing_b:
        raise ValueError("fixed crossing review and route source differs")
    rows_a, rows_b = case_a.get("rows"), case_b.get("rows")
    if not isinstance(rows_a, list) or not isinstance(rows_b, list):
        raise ValueError("original per-frame source rows missing")
    ma, mb = measure_trace(rows_a, crossing_a), measure_trace(rows_b, crossing_b)
    if axis != "speed" and abs(ma["maximum_traversal_speed_mps"]-mb["maximum_traversal_speed_mps"]) > .3:
        raise ValueError("undeclared traversal speed change")
    if axis == "speed":
        if (abs(ma["maximum_traversal_speed_mps"]-mb["maximum_traversal_speed_mps"]) < .5
                or bool(ma["last_100_feet_missing_view_frames"]) != bool(mb["last_100_feet_missing_view_frames"])
                or ma["flagman_on_duty_frames"] != mb["flagman_on_duty_frames"]
                or ma["visible_inactive_signal_frames"] != mb["visible_inactive_signal_frames"]):
            raise ValueError("speed contrast or fixed sight and exception states missing")
    if axis == "sight" and ma["last_100_feet_missing_view_frames"] == mb["last_100_feet_missing_view_frames"]:
        raise ValueError("sight contrast absent in original rays")
    if axis == "flagman" and ma["flagman_on_duty_frames"] == mb["flagman_on_duty_frames"]:
        raise ValueError("flagman duty contrast absent")
    if axis == "signal_state" and ma["visible_inactive_signal_frames"] == mb["visible_inactive_signal_frames"]:
        raise ValueError("crossing signal indication contrast absent")
    if axis == "signal_visibility" and ma["visible_inactive_signal_frames"] == mb["visible_inactive_signal_frames"]:
        raise ValueError("crossing signal visibility contrast absent")
    if axis not in ("flagman",) and ma["flagman_on_duty_frames"] != mb["flagman_on_duty_frames"]:
        raise ValueError("undeclared flagman duty change")
    if axis not in ("signal_state", "signal_visibility") and ma["visible_inactive_signal_frames"] != mb["visible_inactive_signal_frames"]:
        raise ValueError("undeclared signal exception change")
    return {"format": "rail-comparison-audit-v1", "comparison_id": comparison["comparison_id"],
            "case_ids": comparison["case_ids"], "axis": axis,
            "fixed_source_keys": list(FIXED), "measurements": [ma, mb],
            "diagnostic_only": diagnostic_fixture,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
