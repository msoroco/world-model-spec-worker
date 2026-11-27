"""Independent source-bound parked-departure contrasts, without legal verdicts."""
from __future__ import annotations

import json
from pathlib import Path

from parked_construction import ASSIGNMENT
from audit_original_attempt import audit

PAIRS = {
    "rear_wait_vs_intrude": ("rear_wait", "rear_intrude"),
    "rear_wait_vs_clear": ("rear_wait", "rear_clear"),
    "opposing_wait_vs_intrude": ("opposing_wait", "opposing_intrude"),
    "opposing_intrude_vs_nonconflict": ("opposing_intrude", "opposing_nonconflict"),
    "rear_wait_vs_opposing_wait": ("rear_wait", "opposing_wait"),
}
FIXED_SOURCES = ("map", "highway_boundary", "dedication", "public_use",
                 "parking_permission", "vehicle_blueprint")
FIXED_SITE = ("public_highway_status", "public_dedication_reviewed",
              "public_vehicular_use_reviewed", "parking_permitted_at_capture_time",
              "highway_polygon_xy_m", "parking_bay_polygon_xy_m",
              "parked_vehicle_center_xy_m", "ego_departure_entry_xy_m",
              "ego_departure_exit_xy_m")


def _load(path, variant):
    path = Path(path)
    case_id = ASSIGNMENT + "__" + variant
    finding = audit(path, case_id)
    site = json.loads((path / "site.json").read_text())
    plan = json.loads((path / "plan.json").read_text())
    measured = json.loads((path / "activity-measurement.json").read_text())
    return finding, site, plan, measured


def _start(spans):
    return spans[0][0] if spans else None


def _end(spans):
    return spans[-1][1] if spans else None


def compare(comparison_id, original_a, original_b):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact parked-departure comparison")
    first, second = PAIRS[comparison_id]
    a, site_a, plan_a, measure_a = _load(original_a, first)
    b, site_b, plan_b, measure_b = _load(original_b, second)
    for key in FIXED_SOURCES:
        if site_a.get("reviewed_sources", {}).get(key) != site_b.get("reviewed_sources", {}).get(key):
            raise ValueError("fixed reviewed source differs: " + key)
    for key in FIXED_SITE:
        if site_a.get(key) != site_b.get(key):
            raise ValueError("fixed parked highway condition differs: " + key)
    for key in ("ego_initial_parked_center_xy_m", "ego_departure_route_xy_m", "capture"):
        if plan_a.get(key) != plan_b.get(key):
            raise ValueError("fixed constructed capture differs: " + key)
    ia, ib = measure_a["intervals_s"], measure_b["intervals_s"]
    if not ia["parked"] or not ib["parked"] or not ia["moving"] or not ib["moving"]:
        raise ValueError("original parked departure absent")
    if comparison_id in ("rear_wait_vs_intrude", "opposing_wait_vs_intrude"):
        if (not ia["other_approaching"] or not ib["other_approaching"] or
                _start(ia["moving"]) < _end(ia["other_approaching"]) or
                _start(ib["moving"]) >= _end(ib["other_approaching"]) or
                not ib["paths_overlap"]):
            raise ValueError("original waited versus early departure contrast absent")
    elif comparison_id == "rear_wait_vs_clear":
        if not ia["other_approaching"] or ib["other_approaching"]:
            raise ValueError("original rear approach presence contrast absent")
    elif comparison_id == "opposing_intrude_vs_nonconflict":
        if (not ia["paths_overlap"] or ib["paths_overlap"] or
                not ia["other_approaching"] or not ib["other_approaching"]):
            raise ValueError("original route-intersection contrast absent")
    else:
        if (plan_a["other_approach_kind"], plan_b["other_approach_kind"]) != ("rear", "opposing"):
            raise ValueError("original approach direction contrast absent")
        if (_start(ia["moving"]) < _end(ia["other_approaching"]) or
                _start(ib["moving"]) < _end(ib["other_approaching"])):
            raise ValueError("fixed waiting behavior differs")
    return {"comparison_id": comparison_id, "case_ids": [a["case_id"], b["case_id"]],
            "structural_status": "passed", "deliberate_contrast": "observed",
            "physical_completion": False, "legal_conclusion": "unreviewed"}
