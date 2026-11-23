"""Independent saved-metric comparison guard for the red-left attempt pairs."""
from __future__ import annotations


def audit(left, right, expected_left, expected_right):
    for metric, case in ((left, expected_left), (right, expected_right)):
        if metric.get("case_id") != case or metric.get("legal_judgment") != "unresolved":
            raise ValueError("comparison case or legal-state mismatch")
        if metric.get("physical_acceptance_claimed") is not False or metric.get("original_frames", 0) < 2:
            raise ValueError("missing original-frame proof")
        if not metric.get("site_sha256") or not metric.get("trace_sha256"):
            raise ValueError("comparison source binding missing")
        if not metric.get("stop_reference_kind") or not metric.get("extreme_left_lane_id"):
            raise ValueError("comparison fixed geometry missing")
    if left["site_sha256"] != right["site_sha256"] or left["stop_reference_kind"] != right["stop_reference_kind"]:
        raise ValueError("comparison site or stop reference changed")
    if left["trace_sha256"] == right["trace_sha256"]:
        raise ValueError("comparison reuses same original history")
    return {"left_case_id": expected_left, "right_case_id": expected_right,
            "site_sha256": left["site_sha256"], "fixed_stop_reference": left["stop_reference_kind"],
            "requested_difference_physically_confirmed": False,
            "legal_judgment": "unresolved"}
