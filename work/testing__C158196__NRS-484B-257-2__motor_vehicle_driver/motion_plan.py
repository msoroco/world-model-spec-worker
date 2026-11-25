"""Validate the exact authored C158196 subsection 2 source comparison plan."""

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C158196__NRS-484B-257-2__motor_vehicle_driver"
EXPECTED = {
    "active_signal_controls": ("signal-site.xodr", "Green", True, "yield"),
    "signal_off_signed_duty": ("signal-site.xodr", "Off", True, "yield"),
    "signal_elsewhere_no_control": ("visible-site.xodr", "Green", False, "yield"),
    "signal_off_stop_signed_duty": ("stop-site.xodr", "Off", True, "stop"),
    "approaching_traffic_close": ("signal-site.xodr", "Off", True, "yield"),
    "approaching_traffic_far": ("signal-site.xodr", "Off", True, "yield"),
}


def validate(root: Path, site_reader) -> dict:
    root = Path(root)
    plan = json.loads((root / "motion-plan.json").read_text())
    if (plan.get("format") != "c158196-257-2-motion-plan" or
            plan.get("legal_immediate_hazard_cutoff", "missing") is not None or
            plan.get("site_classification_review_pending") is not True):
        raise ValueError("Motion plan confuses engineering and legal judgments")
    rows = plan.get("cases")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED):
        raise ValueError("Incomplete exact C158196 case plan")
    by_suffix = {}
    for row in rows:
        case_id = row.get("case_id", "")
        if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
            raise ValueError("Wrong exact case identity")
        suffix = case_id[len(ASSIGNMENT)+2:]
        if suffix not in EXPECTED or suffix in by_suffix:
            raise ValueError("Unknown or duplicate case variant")
        by_suffix[suffix] = row
        site_name, state, governing, device = EXPECTED[suffix]
        site_path = root / site_name
        if row.get("site_path") != site_name or hashlib.sha256(site_path.read_bytes()).hexdigest() != row.get("site_sha256"):
            raise ValueError("Authored site source hash differs")
        site = site_reader(site_path)
        ego_device = next(item["device"] for item in site["entrances"] if item["lane_key"] == site["ego_lane_key"])
        if site["authored_signal_governs_ego"] is not governing or ego_device != device or row.get("signal_state") != state:
            raise ValueError("Signed entrance or signal comparison differs")
        if row.get("rate_hz") != 20 or row.get("duration_s") != 30 or row.get("engineering_only") is not True:
            raise ValueError("Exact capture duration or engineering status differs")
        if (row.get("ego_start_xy_m") != [-40.0, 1.8] or
                not isinstance(row.get("other_start_xy_m"), list) or
                len(row["other_start_xy_m"]) != 2 or
                row["other_start_xy_m"][0] != 1.8 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in row["other_start_xy_m"]) or
                any(type(row.get(key)) not in (int, float) or
                    not math.isfinite(row[key]) or not 0 < row[key] <= 1
                    for key in ("ego_throttle", "other_throttle")) or
                type(row.get("ego_hold_ticks")) is not int or row["ego_hold_ticks"] < 1 or
                type(row.get("other_hold_ticks")) is not int or row["other_hold_ticks"] < 0):
            raise ValueError("Authored actor route or phase differs")
    if set(by_suffix) != set(EXPECTED):
        raise ValueError("Missing exact case variant")
    baseline = by_suffix["signal_off_signed_duty"]
    for suffix in ("active_signal_controls", "signal_elsewhere_no_control", "signal_off_stop_signed_duty"):
        candidate = by_suffix[suffix]
        for key in ("ego_start_xy_m", "other_start_xy_m", "ego_hold_ticks", "other_hold_ticks",
                    "ego_throttle", "other_throttle", "rate_hz", "duration_s"):
            if candidate[key] != baseline[key]:
                raise ValueError("Signal or sign comparison changed motion: " + key)
    close, far = by_suffix["approaching_traffic_close"], by_suffix["approaching_traffic_far"]
    # Negative y is farther from the junction on the northbound approach.
    if close["other_start_xy_m"][1] <= far["other_start_xy_m"][1]:
        raise ValueError("Approaching separation order differs")
    for key in ("site_path", "signal_state", "ego_start_xy_m", "ego_hold_ticks",
                "other_hold_ticks", "ego_throttle", "other_throttle", "rate_hz", "duration_s"):
        if close[key] != far[key]:
            raise ValueError("Approach sweep changed fixed condition: " + key)
    return {"format": "c158196-257-2-motion-review", "case_ids": [row["case_id"] for row in rows],
            "authored_sites_checked": 3, "physical_motion_verified": False,
            "legal_hazard_judgment": "unresolved"}
