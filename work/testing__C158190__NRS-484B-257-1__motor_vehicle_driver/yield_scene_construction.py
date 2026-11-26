"""Source-gated construction calls for the three selected yield variants.

The adapter is the Native scene owner. This module refuses to convert the
frozen stop-sign cell label into evidence of a proper yield-sign site.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from yield_view_measurement import ASSIGNMENT


VARIANTS = {
    "yield_slow_hazard": ("slow", "close"),
    "yield_stop_hazard": ("stop", "close"),
    "yield_slow_no_hazard": ("slow", "clear"),
}


def _digest(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("original source hash required: " + name)


def _finite_nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("finite nonnegative reviewed " + name + " required")


def validate_site(path: str | Path, case_id: str) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    site = json.loads(raw)
    if site.get("assignment_id") != ASSIGNMENT or site.get("cell_id") != "C158190":
        raise ValueError("original assignment and cell identity required")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if case_id != ASSIGNMENT + "__" + suffix or suffix not in VARIANTS:
        raise ValueError("unknown selected yield case")
    if site.get("review_status") != "reviewed" or site.get("source_kind") != "original_site_survey":
        raise ValueError("original reviewed Native site survey required")
    if site.get("approved_control_variant") != "yield_sign":
        raise ValueError("reviewed yield control variant required for stop-sign catalog cell")
    for name in ("map_source_sha256", "yield_sign_survey_sha256",
                 "marking_survey_sha256", "view_ray_survey_sha256",
                 "through_highway_survey_sha256"):
        _digest(site.get(name), name)
    if site.get("police_control_active") is not False or site.get("traffic_signal_control_active") is not False:
        raise ValueError("officer and signal exclusions require original negative readback")
    if (site.get("stop_line_present") is not False or
            site.get("near_crosswalk_present") is not False or
            site.get("sidewalk_derived_crosswalk_present") is not False):
        raise ValueError("original no-line/no-crosswalk/sidewalk survey required")
    sign = site.get("yield_sign")
    if not isinstance(sign, dict) or not sign.get("blueprint_id") or not sign.get("governed_approach_id"):
        raise ValueError("reviewed proper yield-sign blueprint and approach required")
    if not isinstance(sign.get("transform"), dict) or not all(k in sign["transform"] for k in ("x", "y", "z", "yaw")):
        raise ValueError("reviewed yield-sign transform required")
    for key in ("x", "y", "z", "yaw"):
        value = sign["transform"][key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("finite reviewed yield-sign transform required")
    if not isinstance(site.get("through_vehicle"), dict) or not site["through_vehicle"].get("route_source_id"):
        raise ValueError("reviewed through-highway vehicle route required")
    plans = site.get("case_plans")
    if not isinstance(plans, dict) or suffix not in plans:
        raise ValueError("reviewed exact-case plan required")
    plan = plans[suffix]
    response, phase = VARIANTS[suffix]
    if plan.get("ego_response") != response or plan.get("through_traffic_phase") != phase:
        raise ValueError("reviewed exact-case intervention differs")
    _finite_nonnegative(plan.get("through_start_delay_s"), "through-vehicle timing")
    site["_source_sha256"] = hashlib.sha256(raw).hexdigest()
    return site


def construct(adapter, site_path: str | Path, case_id: str) -> dict:
    """Issue Native construction calls and reject contradictory readback."""
    site = validate_site(site_path, case_id)
    suffix = case_id.rsplit("__", 1)[-1]
    before = adapter.read_control(site["yield_sign"]["governed_approach_id"])
    if before == "stop_sign":
        raise ValueError("active stop sign conflicts with selected yield governance")
    sign_id = adapter.spawn_yield_sign(site["yield_sign"]["blueprint_id"],
                                       site["yield_sign"]["transform"])
    readback = adapter.read_sign(sign_id)
    if readback.get("control") != "yield_sign" or readback.get("governed_approach_id") != site["yield_sign"]["governed_approach_id"]:
        raise ValueError("Native yield-sign governance readback failed")
    markings = adapter.survey_markings(site["yield_sign"]["governed_approach_id"])
    if (markings.get("stop_line_present") is not False or
            markings.get("near_crosswalk_present") is not False or
            markings.get("sidewalk_derived_crosswalk_present") is not False):
        raise ValueError("Native marking readback contradicts source survey")
    stations = adapter.survey_view_stations(site["yield_sign"]["governed_approach_id"])
    if not isinstance(stations, list) or not any(s.get("view_of_through_traffic") is True for s in stations):
        raise ValueError("Native through-highway view readback missing")
    vehicle_id = adapter.spawn_through_vehicle(site["through_vehicle"],
                                               site["case_plans"][suffix]["through_start_delay_s"])
    if not vehicle_id:
        raise ValueError("Native through-vehicle spawn failed")
    return {"case_id": case_id, "site_source_sha256": site["_source_sha256"],
            "yield_sign_actor_id": sign_id, "through_vehicle_actor_id": vehicle_id,
            "planned_response": site["case_plans"][suffix]["ego_response"],
            "planned_through_traffic_phase": site["case_plans"][suffix]["through_traffic_phase"],
            "readback_limit": "Native actor and map readback must be retained with original capture."}
