"""Source-bound construction for a possible C158190 stop-sign branch.

This is a candidate for a corrected branch allocation. It does not replace the
frozen yield-sign assignment or assert that an original site survey exists.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C158190__NRS-484B-257-1__motor_vehicle_driver"
CASES = {
    ASSIGNMENT + "__stop_nearest_view_response": "stop_then_yield",
    ASSIGNMENT + "__stop_nearest_view_uninterrupted": "stop_then_cross",
}
SOURCES = (
    "map_source_sha256",
    "ego_route_source_sha256",
    "stop_sign_survey_sha256",
    "marking_survey_sha256",
    "view_ray_survey_sha256",
    "through_highway_survey_sha256",
)


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("finite original " + label + " required")
    return float(value)


def _check_source_bytes(site, site_path):
    records = site.get("source_records")
    if not isinstance(records, dict) or set(records) != set(SOURCES):
        raise ValueError("six independent original stop-site source records required")
    for key in SOURCES:
        record = records[key]
        if not isinstance(record, dict):
            raise ValueError("original source record missing: " + key)
        name, expected = record.get("path"), record.get("sha256")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("original source path must be local: " + key)
        if not isinstance(expected, str) or len(expected) != 64 or expected != site.get(key):
            raise ValueError("original source hash differs: " + key)
        path = site_path.parent / name
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("original source bytes differ: " + key)


def validate_site(site_path: str | Path, case_id: str) -> dict:
    """Reject missing, synthetic, mutable, or non-stop source packets."""
    path = Path(site_path).resolve()
    if case_id not in CASES:
        raise ValueError("unknown C158190 stop branch case")
    raw = path.read_bytes()
    site = json.loads(raw)
    if (site.get("assignment_id") != ASSIGNMENT or site.get("cell_id") != "C158190"
            or site.get("control") != "stop_sign"):
        raise ValueError("fixed C158190 stop-sign identity required")
    for name in ("intersection_id", "ego_route_id"):
        if not isinstance(site.get(name), str) or not site[name]:
            raise ValueError("reviewed stop-site identity required: " + name)
    if site.get("source_kind") != "original_site_survey" or site.get("review_status") != "reviewed":
        raise ValueError("independently reviewed original stop-site survey required")
    if site.get("police_control_active") is not False or site.get("traffic_signal_control_active") is not False:
        raise ValueError("officer and signal exclusions require negative readback")
    if (site.get("stop_line_present") is not False or site.get("near_crosswalk_present") is not False
            or site.get("sidewalk_derived_crosswalk_present") is not False):
        raise ValueError("no-line and no-crosswalk source survey required")
    sign = site.get("stop_sign")
    if (not isinstance(sign, dict) or not isinstance(sign.get("governed_approach_id"), str)
            or not sign["governed_approach_id"]):
        raise ValueError("proper stop sign and governed approach required")
    if not isinstance(sign.get("transform"), dict) or any(
            not isinstance(sign["transform"].get(axis), (int, float)) or
            isinstance(sign["transform"].get(axis), bool) or
            not math.isfinite(sign["transform"][axis])
            for axis in ("x", "y", "z", "yaw")):
        raise ValueError("reviewed stop-sign transform required")
    stations = site.get("approach_view_stations")
    if not isinstance(stations, list) or len(stations) < 2:
        raise ValueError("two original nearest-view stations required")
    distances = []
    station_ids = set()
    for station in stations:
        if (not isinstance(station, dict) or not isinstance(station.get("station_id"), str)
                or not station["station_id"] or station["station_id"] in station_ids):
            raise ValueError("identified original view station required")
        station_ids.add(station["station_id"])
        distance = _finite(station.get("distance_to_intersection_m"), "view-station distance")
        if distance < 0:
            raise ValueError("nonnegative view-station distance required")
        distances.append(distance)
        if type(station.get("reviewed_visible")) is not bool:
            raise ValueError("reviewed through-traffic visibility required")
    if len(set(distances)) != len(distances):
        raise ValueError("distinct nearest-view distances required")
    if not any(row["reviewed_visible"] for row in stations):
        raise ValueError("reviewed nearest-view point missing")
    through = site.get("through_vehicle")
    if not isinstance(through, dict) or not through.get("route_source_id"):
        raise ValueError("reviewed through-highway route required")
    plans = site.get("case_plans")
    if not isinstance(plans, dict) or case_id not in plans:
        raise ValueError("exact stop-branch case plan required")
    plan = plans[case_id]
    if plan.get("ego_response") != CASES[case_id]:
        raise ValueError("exact stop-branch response differs")
    _finite(plan.get("through_start_delay_s"), "through-vehicle delay")
    hold = _finite(plan.get("stop_hold_s"), "stop hold")
    if hold < 0.25 or hold > 20:
        raise ValueError("bounded engineering stop hold required")
    counterpart = next(other for other in CASES if other != case_id)
    if counterpart not in plans or plans[counterpart].get("ego_response") != CASES[counterpart]:
        raise ValueError("controlled stop-response counterpart required")
    if plan.get("through_start_delay_s") != plans[counterpart].get("through_start_delay_s"):
        raise ValueError("through traffic timing must stay fixed")
    other_hold = _finite(plans[counterpart].get("stop_hold_s"), "counterpart stop hold")
    if (hold <= other_hold) != (CASES[case_id] == "stop_then_cross") or hold == other_hold:
        raise ValueError("stop-response engineering intervention differs")
    _check_source_bytes(site, path)
    site["_site_sha256"] = hashlib.sha256(raw).hexdigest()
    site["_source_path"] = str(path)
    return site


def construct(adapter, site_path: str | Path, case_id: str) -> dict:
    """Issue construction calls and require actual stop governance readback."""
    site = validate_site(site_path, case_id)
    approach = site["stop_sign"]["governed_approach_id"]
    if adapter.read_control(approach) != "stop_sign":
        raise ValueError("Native stop-sign governance readback differs")
    markings = adapter.survey_markings(approach)
    if (not isinstance(markings, dict) or markings.get("stop_line_present") is not False
            or markings.get("near_crosswalk_present") is not False
            or markings.get("sidewalk_derived_crosswalk_present") is not False):
        raise ValueError("Native markings contradict reviewed no-line site")
    def checked_view():
        stations = adapter.survey_view_stations(approach)
        reviewed = {row["station_id"]: row for row in site["approach_view_stations"]}
        if not isinstance(stations, list) or len(stations) != len(reviewed):
            raise ValueError("Native nearest-view station readback missing")
        seen = set()
        visible = []
        for row in stations:
            if not isinstance(row, dict) or row.get("station_id") not in reviewed or row["station_id"] in seen:
                raise ValueError("Native view station identity differs")
            station_id = row["station_id"]
            seen.add(station_id)
            distance = _finite(row.get("distance_to_intersection_m"), "Native view distance")
            expected = _finite(reviewed[station_id]["distance_to_intersection_m"], "reviewed view distance")
            if abs(distance - expected) > 0.25 or type(row.get("view_of_through_traffic")) is not bool:
                raise ValueError("Native view station geometry or visibility differs")
            if row["view_of_through_traffic"]:
                visible.append((distance, station_id))
        if not visible:
            raise ValueError("Native through-highway view readback missing")
        return min(visible)[1]
    reviewed_nearest = min((_finite(row["distance_to_intersection_m"], "reviewed view distance"),
                            row["station_id"]) for row in site["approach_view_stations"]
                           if row["reviewed_visible"])[1]
    if checked_view() != reviewed_nearest:
        raise ValueError("Native nearest-view point differs from reviewed source")
    plan = site["case_plans"][case_id]
    vehicle_id = adapter.spawn_through_vehicle(site["through_vehicle"], plan["through_start_delay_s"])
    if not vehicle_id:
        raise ValueError("Native through-vehicle spawn failed")
    try:
        if checked_view() != reviewed_nearest:
            raise ValueError("Native through-vehicle sightline differs from reviewed source")
    except BaseException:
        if hasattr(adapter, "release_through_vehicle"):
            adapter.release_through_vehicle(vehicle_id)
        raise
    return {
        "case_id": case_id,
        "cell_id": "C158190",
        "control": "stop_sign",
        "site_source_sha256": site["_site_sha256"],
        "through_vehicle_actor_id": vehicle_id,
        "nearest_view_station_id": reviewed_nearest,
        "planned_response": plan["ego_response"],
        "physical_status": "original motion and sightline pending",
    }
