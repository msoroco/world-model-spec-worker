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


def audit_receiving_direction(one_way, two_way, expected_one_way, expected_two_way):
    """Compare separately reviewed receiving roads with common approach sources."""
    for metric, case, direction, route in (
        (one_way, expected_one_way, "one_way_left", "one_way_routes"),
        (two_way, expected_two_way, "two_way", "two_way_routes"),
    ):
        if (metric.get("case_id") != case or metric.get("receiving_direction") != direction
                or metric.get("legal_judgment") != "unresolved"
                or metric.get("physical_acceptance_claimed") is not False
                or metric.get("original_frames", 0) < 2
                or not metric.get("site_sha256") or not metric.get("trace_sha256")):
            raise ValueError("receiving-direction case or original proof differs")
        hashes = metric.get("source_hashes")
        if not isinstance(hashes, dict) or set(hashes) != {
                "opendrive", "official_signal", "stop_reference", route}:
            raise ValueError("receiving-direction source inventory differs")
        if any(not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
            raise ValueError("receiving-direction source hash missing")
    fixed = ("opendrive", "official_signal", "stop_reference")
    if any(one_way["source_hashes"][key] != two_way["source_hashes"][key] for key in fixed):
        raise ValueError("fixed approach, signal or stop source changed")
    if one_way["trace_sha256"] == two_way["trace_sha256"] or one_way["site_sha256"] == two_way["site_sha256"]:
        raise ValueError("receiving-direction comparison reuses original history or site")
    if one_way.get("stop_reference_kind") != two_way.get("stop_reference_kind"):
        raise ValueError("stop reference kind changed")
    return {"comparison_id": "receiving_direction", "case_ids": [expected_one_way, expected_two_way],
            "fixed_source_sha256": {key: one_way["source_hashes"][key] for key in fixed},
            "one_way_site_sha256": one_way["site_sha256"],
            "two_way_site_sha256": two_way["site_sha256"],
            "requested_difference_physically_confirmed": False,
            "legal_judgment": "unresolved"}
