"""Independent comparison checks; no legal right-of-way label is inferred."""

PAIRS = {
    "vehicle_at_exhibition": ("dual_clear", "dual_vehicle_present", None, "intersection"),
    "pedestrian_at_exhibition": ("dual_clear", "dual_pedestrian_present", None, "adjacent_crosswalk"),
    "exhibition_timing": ("dual_pedestrian_present", "dual_pedestrian_late", "adjacent_crosswalk", "outside"),
}


class ComparisonError(ValueError):
    pass


def audit_pair(comparison_id, left, right):
    if comparison_id not in PAIRS:
        raise ComparisonError("unknown comparison")
    left_case, right_case, left_region, right_region = PAIRS[comparison_id]
    if (left.get("case_suffix"), right.get("case_suffix")) != (left_case, right_case):
        raise ComparisonError("wrong exact case pair")
    fixed = ("map_sha256", "route_sha256", "signal_survey_sha256", "crosswalk_sha256", "movement_permission_sha256", "camera_profile_sha256", "duration_frames", "official_head_id", "ego_approach_id", "arrow_direction")
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError("fixed condition differs: " + key)
    for record, expected in ((left, left_region), (right, right_region)):
        observations = record.get("records")
        if not isinstance(observations, list) or len(observations) != record["duration_frames"]:
            raise ComparisonError("incomplete original frames")
        if not all(r.get("dual_green") is True for r in observations):
            raise ComparisonError("simultaneous green aspects not observed throughout")
        exhibition = record.get("exhibition")
        if not exhibition or not isinstance(exhibition.get("other_users"), list):
            raise ComparisonError("exhibition source absent")
        regions = [u["region"] for u in exhibition["other_users"]]
        if (regions if expected else []) != ([expected] if expected else []) or (expected is None and regions):
            raise ComparisonError("user region at exhibition differs")
        if record.get("permission_verdict") is not None or record.get("right_of_way_verdict") is not None:
            raise ComparisonError("unsupported legal verdict")
    return {"comparison_id": comparison_id, "source_frames_checked": left["duration_frames"] + right["duration_frames"], "physical_acceptance": False, "legal_verdict": None}
