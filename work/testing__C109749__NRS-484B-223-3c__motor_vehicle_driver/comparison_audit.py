"""Independent CPU comparison of original measured center-lane travel.

This checks packet completeness and controlled differences. It does not make a
statutory verdict or accept a physical recording.
"""

from math import isfinite


def audit_numeric_triple(rows):
    expected = ("below_50ft", "at_50ft", "above_50ft")
    if set(rows) != set(expected):
        raise ValueError("comparison requires exact below/at/above cases")
    fixed = ("native_map_sha256", "highway_review_sha256", "lane_design_sha256",
             "entry_route_sha256", "receiving_vehicle_route_sha256", "camera_plan_sha256")
    for suffix in expected:
        row = rows[suffix]
        if not row.get("original_trace_source") or not row.get("original_trace_sha256"):
            raise ValueError("missing original trace binding: " + suffix)
        if row.get("merge_observed") is not True or row.get("censored") is not False:
            raise ValueError("numeric case needs observed merge: " + suffix)
        if not all(row.get(key) for key in fixed):
            raise ValueError("missing fixed condition: " + suffix)
        distance = row.get("distance_ft")
        if not isinstance(distance, (float, int)) or not isfinite(distance) or distance < 0:
            raise ValueError("invalid original distance: " + suffix)
        if row.get("boundary_ft") != 50.0:
            raise ValueError("wrong statutory boundary: " + suffix)
    for key in fixed:
        if len({rows[suffix][key] for suffix in expected}) != 1:
            raise ValueError("fixed condition differs: " + key)
    if len({rows[suffix]["original_trace_sha256"] for suffix in expected}) != 3:
        raise ValueError("case traces must be distinct")
    measured = {suffix: rows[suffix]["distance_ft"] for suffix in expected}
    # This tolerance is only a capture probe for the authored at-boundary case.
    # It does not resolve vehicle reference-point or legal interpretation.
    if not (measured["below_50ft"] < 50.0 and
            abs(measured["at_50ft"] - 50.0) <= 0.25 and
            measured["above_50ft"] > 50.0 and
            measured["below_50ft"] < measured["at_50ft"] < measured["above_50ft"]):
        raise ValueError("original measurements do not realize below/at/above probes")
    return {"comparison_id": "post_turn_center_lane_distance", "fixed_conditions_verified": list(fixed),
            "measured_distance_ft": measured, "at_boundary_probe_tolerance_ft": 0.25,
            "original_sources": {suffix: rows[suffix]["original_trace_source"] for suffix in expected},
            "legal_judgment": None}


def audit_merge_observation(merged, no_merge):
    for row in (merged, no_merge):
        if not row.get("original_trace_source") or not row.get("original_trace_sha256"):
            raise ValueError("missing original trace binding")
    for key in ("native_map_sha256", "highway_review_sha256", "lane_design_sha256",
                "entry_route_sha256", "receiving_vehicle_route_sha256", "camera_plan_sha256"):
        if not merged.get(key) or merged[key] != no_merge.get(key):
            raise ValueError("fixed condition differs: " + key)
    if merged.get("merge_observed") is not True or merged.get("censored") is not False:
        raise ValueError("reference merge not observed")
    if no_merge.get("merge_observed") is not False or no_merge.get("censored") is not True or no_merge.get("merge_frame") is not None:
        raise ValueError("no-merge case must be censored")
    return {"comparison_id": "merge_observation", "fixed_conditions_verified": True,
            "merge_observed": [True, False], "legal_judgment": None}
