"""Independent source-bound contrasts for the five exact business-alley pairs."""
from __future__ import annotations

import json
from pathlib import Path

from alley_construction import ASSIGNMENT
from audit_original_attempt import audit

PAIRS = {
    "passenger_active_vs_waiting": ("passenger_active_stop", "passenger_wait_stand"),
    "passenger_stop_vs_driver_exit": ("passenger_active_stop", "passenger_driver_exit_park"),
    "passenger_vs_goods": ("passenger_active_stop", "goods_active_load"),
    "goods_active_vs_interrupted": ("goods_active_load", "goods_wait_interrupted"),
    "ordinance_override": ("passenger_active_stop", "ordinance_passenger_authorized"),
}
FIXED_SOURCES = ("map", "alley", "business_frontage", "jurisdiction",
                 "vehicle_blueprint", "passenger_actor", "goods_actor")


def _load(root, expected):
    root = Path(root)
    case_id = ASSIGNMENT + "__" + expected
    finding = audit(root, case_id)
    site = json.loads((root / "site.json").read_text())
    plan = json.loads((root / "plan.json").read_text())
    measure = json.loads((root / "activity-measurement.json").read_text())
    return finding, site, plan, measure


def _first(spans):
    return spans[0][0] if spans else None


def compare(comparison_id, original_a, original_b):
    """Prove a controlled physical contrast, leaving legal review unresolved."""
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact business-alley comparison")
    first, second = PAIRS[comparison_id]
    a, site_a, plan_a, measure_a = _load(original_a, first)
    b, site_b, plan_b, measure_b = _load(original_b, second)
    for key in FIXED_SOURCES:
        if site_a.get("reviewed_sources", {}).get(key) != site_b.get("reviewed_sources", {}).get(key):
            raise ValueError("fixed reviewed source differs: " + key)
    for key in ("alley_kind", "business_district_reviewed", "jurisdiction_reviewed",
                "centerline_start_m", "centerline_end_m", "loading_station_m",
                "loading_bay_reviewed", "passenger_zone_xy_m", "goods_zone_xy_m"):
        if site_a.get(key) != site_b.get(key):
            raise ValueError("fixed surveyed alley condition differs: " + key)
    for key in ("target_xy_m", "approach_direction", "capture"):
        if plan_a.get(key) != plan_b.get(key):
            raise ValueError("fixed constructed capture differs: " + key)
    ia, ib = measure_a["intervals_s"], measure_b["intervals_s"]
    if not ia["halt"] or not ib["halt"]:
        raise ValueError("original vehicle halt absent")
    if comparison_id != "ordinance_override":
        if (site_a.get("ordinance_status"), site_b.get("ordinance_status")) != (
                "reviewed_no_applicable_override", "reviewed_no_applicable_override"):
            raise ValueError("fixed ordinance condition differs")
    if comparison_id == "passenger_active_vs_waiting":
        if (_first(ia["passenger_contact"]) is None or
                _first(ib["passenger_contact"]) is None or
                _first(ia["passenger_contact"]) >= _first(ib["passenger_contact"])):
            raise ValueError("original passenger engagement contrast absent")
    elif comparison_id == "passenger_stop_vs_driver_exit":
        if ia["driver_outside"] or not ib["driver_outside"]:
            raise ValueError("original driver-exit contrast absent")
    elif comparison_id == "passenger_vs_goods":
        if (not ia["passenger_contact"] or ia["goods_contact"] or
                ib["passenger_contact"] or not ib["goods_contact"]):
            raise ValueError("original passenger versus goods contrast absent")
    elif comparison_id == "goods_active_vs_interrupted":
        if len(ia["goods_contact"]) != 1 or len(ib["goods_contact"]) < 2:
            raise ValueError("original continuous versus interrupted goods contrast absent")
        if not all(ib["goods_contact"][i][1] < ib["goods_contact"][i + 1][0]
                   for i in range(len(ib["goods_contact"]) - 1)):
            raise ValueError("original goods idle interval absent")
    else:
        if (site_a.get("ordinance_status") != "reviewed_no_applicable_override" or
                site_b.get("ordinance_status") != "reviewed_authorizes_passenger_loading" or
                "ordinance" not in site_b.get("reviewed_sources", {}) or
                not ia["passenger_contact"] or not ib["passenger_contact"] or
                measure_a["ordinance_applicable_frames"] != 0 or
                measure_b["ordinance_applicable_frames"] == 0):
            raise ValueError("reviewed ordinance and original activity contrast absent")
    return {"comparison_id": comparison_id, "case_ids": [a["case_id"], b["case_id"]],
            "structural_status": "passed", "deliberate_contrast": "observed",
            "physical_completion": False, "legal_conclusion": "unreviewed"}
