"""C229126 target selection for a same-direction left pass.

The numeric targets are construction controls. They do not define the law's
safe distance or safely clear language.
"""

TARGETS = {
    "left_pass_wide": (1.5, 1.0),
    "left_pass_narrow": (0.5, 1.0),
    "return_before_clear": (1.0, -0.5),
    "return_after_clear": (1.0, 1.5),
}


def target(case_suffix, *, passed_abreast, body_clearance_m,
           right_lane_id, left_lane_id):
    if case_suffix not in TARGETS:
        raise ValueError("Unknown exact C229126 overtake case")
    if right_lane_id == left_lane_id or not all(
            isinstance(value, int) for value in (right_lane_id, left_lane_id)):
        raise ValueError("Distinct mapped travel lanes required")
    left_gap, return_clearance = TARGETS[case_suffix]
    if passed_abreast and body_clearance_m >= return_clearance:
        return {"phase": "return_right", "lane_id": right_lane_id,
                "target_left_gap_m": None,
                "requested_return_clearance_m": return_clearance}
    return {"phase": "pass_left", "lane_id": left_lane_id,
            "target_left_gap_m": left_gap,
            "requested_return_clearance_m": return_clearance}
