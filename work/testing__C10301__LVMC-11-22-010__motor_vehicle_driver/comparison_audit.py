"""Independent saved-result audit for the alley attention observation contrast.

This checks source and fixed-condition integrity. Measured exterior differences
remain observations; they do not resolve a driver's interior attention state.
"""
from __future__ import annotations

import math


ASSIGNMENT = "testing__C10301__LVMC-11-22-010__motor_vehicle_driver"
STEADY = ASSIGNMENT + "__steady_travel"
VARIATION = ASSIGNMENT + "__steering_variation"
CASES = (STEADY, VARIATION)
FIXED = ("site_source_sha256", "alley_route_source_sha256",
         "access_aisle_source_sha256", "parking_designation_source_sha256",
         "municipal_jurisdiction_source_sha256", "camera_ids",
         "duration_frames", "fps", "nominal_speed_m_s")


def _digest(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("missing SHA256 for " + label)


def audit(measurements: dict, captures: dict) -> dict:
    if set(measurements) != set(CASES) or set(captures) != set(CASES):
        raise ValueError("both exact comparison cases required")
    source_hashes = []
    for case_id in CASES:
        measurement, capture = measurements[case_id], captures[case_id]
        if measurement.get("case_id") != case_id or capture.get("case_id") != case_id:
            raise ValueError("exact case identity mismatch")
        source = measurement.get("source")
        if not isinstance(source, dict) or not source.get("path"):
            raise ValueError("original operation source missing")
        _digest(source.get("sha256"), "operation source")
        if source["sha256"] != capture.get("operation_source_sha256"):
            raise ValueError("measurement source differs from capture")
        source_hashes.append(source["sha256"])
        if measurement.get("attention_state") != "unobserved" or measurement.get("legal_judgment") != "unresolved":
            raise ValueError("unsupported mental-state or legal claim")
        observed = measurement.get("observed_exterior", {})
        yaw = observed.get("max_abs_yaw_rate_rad_s")
        if type(yaw) not in (int, float) or not math.isfinite(yaw) or yaw < 0:
            raise ValueError("original yaw observation missing")
        if type(measurement.get("frame_count")) is not int or measurement["frame_count"] < 2:
            raise ValueError("original frame count missing")
        if capture.get("fps") != 20 or capture.get("duration_frames") != measurement["frame_count"]:
            raise ValueError("capture and original 20 Hz frames differ")
        for key in FIXED:
            if key not in capture or not capture[key]:
                raise ValueError("missing fixed comparison condition: " + key)
        for key in FIXED[:5]:
            _digest(capture[key], key)
    if source_hashes[0] == source_hashes[1]:
        raise ValueError("two planned recordings cannot share one source")
    for key in FIXED:
        if captures[STEADY][key] != captures[VARIATION][key]:
            raise ValueError("undeclared fixed-condition difference: " + key)
    if captures[STEADY].get("requested_lateral_profile") != "steady" or \
            captures[VARIATION].get("requested_lateral_profile") != "variation":
        raise ValueError("declared control contrast missing")
    return {"comparison_id": "alley_lateral_control_observation",
            "case_ids": list(CASES), "source_hashes": source_hashes,
            "fixed_conditions_verified": list(FIXED),
            "requested_control_difference": "steady versus bounded variation",
            "observed_max_abs_yaw_rate_rad_s": {
                case_id: measurements[case_id]["observed_exterior"]["max_abs_yaw_rate_rad_s"]
                for case_id in CASES},
            "interior_attention": "unobserved",
            "legal_judgment": "unresolved",
            "physical_realization": "requires_original_capture_review"}
