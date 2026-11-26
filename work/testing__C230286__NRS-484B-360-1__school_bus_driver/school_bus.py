"""Source-gated Native school-bus route and pupil-trip construction."""

import hashlib
import json
import math
from pathlib import Path

from package_spec import AID


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric source value required")
    return float(value)


def sealed_json(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("source sha256 mismatch")
    return json.loads(raw)


def construct(site, case):
    """Return a request only when map, school-bus and trip facts are separately sourced."""
    if site.get("assignment_id") != AID or site.get("case_id") != case:
        raise ValueError("exact case/site identity differs")
    if site.get("source_kind") != "original_native_map_geometry" or site.get("reviewed_original_native_site") is not True:
        raise ValueError("reviewed original Native site required")
    if not site.get("source_id") or not site.get("map_name") or not site.get("map_sha256"):
        raise ValueError("Native map provenance required")
    road = site.get("road_route")
    if not isinstance(road, dict) or road.get("source_kind") != "native_map_lane_geometry" or road.get("continuous_drivable") is not True:
        raise ValueError("continuous surveyed drivable route required")
    if number(road.get("clear_run_length_m")) < 900 or number(road.get("minimum_width_m")) < 3.0:
        raise ValueError("900-metre bus speed corridor and width required")
    sidewalk = site.get("sidewalk")
    if not isinstance(sidewalk, dict) or not sidewalk.get("source_id") or sidewalk.get("relation") not in ("access", "crossing", "parking"):
        raise ValueError("source-surveyed sidewalk relation required")
    classification = site.get("school_bus_classification")
    if not isinstance(classification, dict) or not classification.get("qualifying_definition_branch") or not classification.get("source") or classification.get("all_exclusions_reviewed") is not True:
        raise ValueError("complete sourced school-bus definition and exclusions required")
    if not classification.get("reviewed_facts") or not classification.get("exclusion_dispositions"):
        raise ValueError("school-bus classification facts and exclusions absent")
    if not site.get("driver_actor_id") or not site.get("bus_identity_source"):
        raise ValueError("driver and school-bus identity sources required")
    trip = site.get("trip")
    if not isinstance(trip, dict) or trip.get("direction") not in ("to_school", "from_school") or not trip.get("source"):
        raise ValueError("sourced to-or-from-school trip required")
    if type(trip.get("pupil_count")) is not int or trip["pupil_count"] < 0 or not trip.get("pupil_presence_source"):
        raise ValueError("separate pupil count and presence source required")
    intervals = trip.get("active_transport_intervals_s")
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("sourced pupil-transport intervals required")
    for interval in intervals:
        if not isinstance(interval, list) or len(interval) != 2 or not 0 <= number(interval[0]) < number(interval[1]) <= 45:
            raise ValueError("bounded transport interval required")
    case_suffix = case.removeprefix(AID + "__")
    targets = {"pupil_trip_54_mph": (54, True), "pupil_trip_55_mph": (55, True),
               "pupil_trip_56_mph": (56, True), "nontransport_56_mph": (56, False)}
    if case_suffix not in targets:
        raise ValueError("unsupported exact school-bus case")
    target_mph, active = targets[case_suffix]
    if site.get("requested_target_mph") != target_mph or site.get("requested_active_transport_phase") is not active:
        raise ValueError("site request differs from exact case")
    if active and trip["pupil_count"] < 1:
        raise ValueError("active pupil transportation requires sourced pupil presence")
    if not active and any(lo <= 30 < hi for lo, hi in intervals):
        raise ValueError("nontransport speed interval overlaps sourced pupil trip")
    spawn = site.get("native_spawn")
    if not isinstance(spawn, dict) or not spawn.get("source_id") or not spawn.get("blueprint_id") or not isinstance(spawn.get("pose_xyz_ypr"), list) or len(spawn["pose_xyz_ypr"]) != 6:
        raise ValueError("source-backed bus blueprint and pose required")
    for value in spawn["pose_xyz_ypr"]:
        number(value)
    return {"case_id": case, "target_speed_mph": target_mph,
            "target_speed_mps": target_mph / 2.2369362920544,
            "transport_intervals_s": intervals, "requested_active_transport_phase": active,
            "native_readback_required": True}
