"""Saved-only fixed-condition comparison of two C157964 Native attempts."""

import json
from pathlib import Path

from saved_audit import audit_saved
from yield_view import CASES, require


PAIRS = {
    "slow_vs_stop": (CASES[0], CASES[1], "approach_policy"),
    "through_phase": (CASES[0], CASES[2], "through_state"),
    "officer_exception": (CASES[0], CASES[3], "officer_controls"),
}


def audit_pair(comparison_id, left_attempt, right_attempt, *, allow_diagnostic=False,
               expected_site_hashes=None):
    require(comparison_id in PAIRS, "unknown exact comparison")
    left_case, right_case, varied = PAIRS[comparison_id]
    require(allow_diagnostic or
            (isinstance(expected_site_hashes, (list, tuple)) and
             len(expected_site_hashes) == 2),
            "independent reviewed site hash pair missing")
    expected = expected_site_hashes or (None, None)
    left = audit_saved(left_attempt, left_case, allow_diagnostic=allow_diagnostic,
                       expected_site_packet_sha256=expected[0])
    right = audit_saved(right_attempt, right_case, allow_diagnostic=allow_diagnostic,
                        expected_site_packet_sha256=expected[1])
    require(left["diagnostic_fixture"] == right["diagnostic_fixture"],
            "comparison mixes original and diagnostic attempts")
    require(left["native_seal_sha256"] != right["native_seal_sha256"],
            "comparison reuses one original attempt")
    left_site = json.loads((Path(left_attempt) / "reviewed-site-packet.json").read_text())["site"]
    right_site = json.loads((Path(right_attempt) / "reviewed-site-packet.json").read_text())["site"]
    fixed = ("jurisdiction", "yield_sign", "stop_line_absence", "crosswalk_absence",
             "nearest_view_location", "through_highway", "sight_observation",
             "traffic_signal_control", "ego_vehicle")
    if varied != "officer_controls":
        fixed += ("officer_control",)
    for role in fixed:
        require(left_site[role + "_source_sha256"] == right_site[role + "_source_sha256"],
                "fixed original source differs: " + role)
    for key in ("route_xy", "nearest_view_station_m", "physical_reference_station_m",
                "camera_dimensions", "through_spawn_xy", "yield_sign_present",
                "stop_line_present", "near_crosswalk_present", "signal_controls"):
        require(left_site[key] == right_site[key], "fixed construction differs: " + key)
    left_measure = json.loads((Path(left_attempt) / "measurement.json").read_text())
    right_measure = json.loads((Path(right_attempt) / "measurement.json").read_text())
    require(getattr(left_case, varied) != getattr(right_case, varied),
            "declared comparison variable does not differ")
    if varied == "approach_policy":
        require(right_measure["minimum_original_approach_speed_mps"] <= .1 and
                left_measure["minimum_original_approach_speed_mps"] > .1,
                "observed slow/stop difference missing")
    elif varied == "officer_controls":
        require(left_measure["officer_controls_observed"] is False and
                right_measure["officer_controls_observed"] is True,
                "observed officer-control difference missing")
    # The through-phase difference is checked across every saved row by audit_saved.
    return {"format": "c157964-saved-comparison-audit-v1",
            "comparison_id": comparison_id,
            "case_ids": [left_case.case_id, right_case.case_id],
            "varied": varied, "diagnostic_fixture": left["diagnostic_fixture"],
            "decoded_camera_frames": left["decoded_camera_frames"] + right["decoded_camera_frames"],
            "source_integrity": True, "physical_difference": "unverified",
            "legal_judgment": None}
