"""Source-gated Native scene and original-frame measurements for NRS 484B.250(4).

All distances use the reviewed approach station, increasing toward the junction.
This module measures physical facts; it does not decide whether proceeding was cautious.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path


ASSIGNMENT = "testing__C24811__NRS-484B-250-4__motor_vehicle_driver"
RATE_HZ = 20
FULL_FRAMES = 900
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = (
    "map_geometry", "signal_installation", "signal_governance",
    "signal_head_cover", "signal_operation", "through_highway",
    "sightline_survey", "stop_reference", "ego_route",
    "other_vehicle_route", "ego_vehicle_class", "driver_control",
    "physical_occluder", "blind_intersection",
)


@dataclass(frozen=True)
class Case:
    name: str
    reference: str
    other_state: str
    ego_policy: str


CASES = (
    Case("line_prior_stop_yield", "stop_line", "prior_stop", "yield"),
    Case("line_occupied_yield", "stop_line", "within", "yield"),
    Case("line_prior_stop_no_yield", "stop_line", "prior_stop", "enter"),
    Case("line_clear_enter", "stop_line", "none", "enter"),
    Case("crosswalk_prior_stop_yield", "near_crosswalk", "prior_stop", "yield"),
    Case("viewpoint_prior_stop_yield", "nearest_view_point", "prior_stop", "yield"),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def _source_records(site, site_path):
    records = site.get("source_records")
    require(isinstance(records, dict) and set(SOURCES) <= set(records),
            "reviewed source inventory incomplete")
    root = Path(site_path).resolve().parent
    for name in SOURCES:
        record = records[name]
        require(isinstance(record, dict), "invalid source record: " + name)
        digest = record.get("sha256")
        relative = Path(record.get("path", ""))
        require(isinstance(digest, str) and len(digest) == 64 and
                not relative.is_absolute() and ".." not in relative.parts and
                relative.parts, "invalid reviewed source path/hash: " + name)
        path = (root / relative).resolve()
        require(path.is_file() and path.is_relative_to(root) and
                sha256(path.read_bytes()).hexdigest() == digest and
                site.get(name + "_source_sha256") == digest,
                "reviewed source bytes changed: " + name)


def validate_site(site, site_path, case: Case, *, map_bytes=None, readback=None):
    """Reject unsupported signal, stop-reference and interaction geometry.

    The packet is a reviewed input supplied by the Native operator, not a
    generated stand-in for official device or sightline evidence.
    """
    require(case in CASES, "unknown exact inoperative-signal case")
    require(site.get("source_kind") == "reviewed_original_native_signal_site" and
            site.get("assignment_id") == ASSIGNMENT and
            site.get("case_id") == ASSIGNMENT + "__" + case.name,
            "reviewed site/case identity mismatch")
    require(site.get("catalog_control") == "traffic_light",
            "C24811 requires the frozen traffic-light control")
    _source_records(site, site_path)
    for key in ("signal_id", "governed_approach", "driver_id", "ego_vehicle_id",
                "other_vehicle_id", "road_id", "lane_id", "through_highway_id"):
        require(site.get(key), "reviewed site missing " + key)
    entrances = site.get("entrance_ids")
    heads = site.get("governing_head_ids")
    require(isinstance(entrances, list) and len(entrances) >= 2 and
            len(set(entrances)) == len(entrances) and
            isinstance(heads, list) and heads and len(set(heads)) == len(heads) and
            all(isinstance(item, str) and item for item in entrances + heads),
            "complete intersection entrance and governing-head inventory missing")
    require(site["ego_vehicle_id"] != site["other_vehicle_id"],
            "interacting vehicle must be distinct")
    require(site.get("signal_installed") is True and
            site.get("vehicular_heads_uncovered") is True and
            site.get("complete_inoperability_at_entry") is True and
            site.get("signal_governs_approach") is True,
            "installed uncovered governing and fully inoperative signal required")
    require(site.get("through_highway_reviewed") is True and
            site.get("sightline_reviewed") is True and
            site.get("blind_intersection_reviewed") is True and
            site.get("physical_occluder_reviewed") is True,
            "reviewed blind intersection, occluder and through-highway sightline required")
    entry = site.get("intersection_entry_m")
    require(number(entry), "surveyed intersection entry missing")
    line = site.get("stop_line_m")
    crosswalk = site.get("near_crosswalk_m")
    view = site.get("nearest_view_point_m")
    require(all(x is None or number(x) for x in (line, crosswalk, view)),
            "invalid surveyed stop references")
    if case.reference == "stop_line":
        require(number(line) and line < entry, "marked stop line missing before entry")
        reference = line
    elif case.reference == "near_crosswalk":
        require(line is None and number(crosswalk) and crosswalk < entry,
                "near-side crosswalk hierarchy not established")
        reference = crosswalk
    else:
        require(line is None and crosswalk is None and number(view) and view < entry,
                "nearest-view stop hierarchy not established")
        reference = view
    require(site.get("other_state") == case.other_state and
            site.get("ego_policy") == case.ego_policy,
            "reviewed other-vehicle or ego policy changed")
    ego_route = site.get("ego_route_station_m")
    other_route = site.get("other_route_station_m")
    require(isinstance(ego_route, list) and len(ego_route) >= 2 and
            all(number(x) for x in ego_route) and
            ego_route[0] < reference < entry < ego_route[-1] and
            all(a < b for a, b in zip(ego_route, ego_route[1:])),
            "connected governed ego approach route missing")
    require(isinstance(other_route, list) and len(other_route) >= 2 and
            all(number(x) for x in other_route) and
            all(a < b for a, b in zip(other_route, other_route[1:])),
            "connected interacting vehicle route missing")
    if map_bytes is not None:
        require(sha256(map_bytes).hexdigest() == site.get("map_sha256"),
                "loaded Native map differs from reviewed map")
    if readback is not None:
        for key in ("signal_id", "governed_approach", "road_id", "lane_id",
                    "stop_line_m", "near_crosswalk_m", "nearest_view_point_m",
                    "intersection_entry_m", "through_highway_id",
                    "vehicular_heads_uncovered", "signal_governs_approach",
                    "blind_intersection_reviewed", "physical_occluder_reviewed",
                    "entrance_ids", "governing_head_ids"):
            require(readback.get(key) == site.get(key),
                    "Native site readback mismatch: " + key)
    return reference


def measure_original(site, site_path, case, ego_rows, other_rows, *, diagnostic=False):
    reference = validate_site(site, site_path, case)
    count = 9 if diagnostic else FULL_FRAMES
    require(len(ego_rows) == len(other_rows) == count,
            "original 20 Hz ego/other history incomplete")
    first_frame = ego_rows[0].get("original_frame")
    first_time = ego_rows[0].get("time_s")
    require(type(first_frame) is int and number(first_time),
            "original frame/time origin missing")
    stop = entry = other_prior_stop = None
    other_inside_frames = []
    ego_moving = other_moving = False
    for index, (ego, other) in enumerate(zip(ego_rows, other_rows)):
        frame = first_frame + index
        time_s = first_time + index / RATE_HZ
        require(ego.get("original_frame") == other.get("original_frame") == frame and
                number(ego.get("time_s")) and number(other.get("time_s")) and
                abs(ego["time_s"] - time_s) <= .005 and
                abs(other["time_s"] - time_s) <= .005,
                "original ego/other 20 Hz frame join invalid")
        for name in SOURCES:
            expected = site[name + "_source_sha256"]
            require(ego.get(name + "_source_sha256") == expected and
                    other.get(name + "_source_sha256") == expected,
                    "original source changed: " + name)
        require(ego.get("vehicle_id") == site["ego_vehicle_id"] and
                other.get("vehicle_id") == site["other_vehicle_id"] and
                ego.get("signal_id") == other.get("signal_id") == site["signal_id"] and
                ego.get("approach_id") == site["governed_approach"],
                "original vehicle/signal governance mismatch")
        for row in (ego, other):
            require(number(row.get("front_m")) and
                    number(row.get("speed_mps")) and row["speed_mps"] >= 0,
                    "original vehicle front/speed missing")
        require(type(ego.get("signal_installed")) is bool and
                type(ego.get("signal_uncovered")) is bool and
                type(ego.get("signal_operating")) is bool and
                type(ego.get("all_heads_wholly_inoperative")) is bool and
                isinstance(ego.get("governing_head_operating"), dict) and
                set(ego["governing_head_operating"]) == set(site["governing_head_ids"]) and
                all(type(v) is bool for v in ego["governing_head_operating"].values()),
                "original signal installation/cover/operation missing")
        if ego["speed_mps"] > .01:
            ego_moving = True
        if other["speed_mps"] > .01:
            other_moving = True
        if ego_moving and ego["speed_mps"] <= .01 and stop is None:
            stop = ego
        if other_moving and other["speed_mps"] <= .01 and other_prior_stop is None:
            other_prior_stop = other
        if other.get("within_intersection") is True:
            other_inside_frames.append(other["original_frame"])
        require(type(other.get("within_intersection")) is bool,
                "original other-vehicle intersection occupancy missing")
        if ego["front_m"] >= site["intersection_entry_m"] and entry is None:
            entry = ego
    require(entry is not None, "original intersection entry not observed")
    require(entry["signal_installed"] and entry["signal_uncovered"] and
            not entry["signal_operating"] and
            entry["all_heads_wholly_inoperative"] and
            not any(entry["governing_head_operating"].values()),
            "installed uncovered inoperative signal at entry not observed")
    require(stop is not None and stop["original_frame"] < entry["original_frame"],
            "ego complete pre-entry cessation not observed")
    position_ok = stop["front_m"] <= reference
    require(position_ok, "original stop beyond statutory reference")
    inside_during_departure = any(stop["original_frame"] <= frame <=
                                  entry["original_frame"]
                                  for frame in other_inside_frames)
    priority = ((other_prior_stop is not None and
                 other_prior_stop["original_frame"] < stop["original_frame"])
                or inside_during_departure)
    require(priority is (case.other_state != "none"),
            "original other-vehicle priority state differs from case")
    if case.other_state == "prior_stop":
        require(other_prior_stop is not None and
                other_prior_stop["original_frame"] < stop["original_frame"],
                "prior completed stop history missing")
    if case.other_state == "within":
        require(inside_during_departure,
                "within-intersection vehicle occupancy missing")
    other_clear_frame = next((row["original_frame"] for row in other_rows
                              if row.get("cleared_conflict_zone") is True), None)
    require(all(type(row.get("cleared_conflict_zone")) is bool
                for row in other_rows),
            "original other-vehicle conflict-zone clearance missing")
    if case.other_state == "none":
        yield_sequence = None
    else:
        yield_sequence = (other_clear_frame is not None and
                          other_clear_frame < entry["original_frame"])
        require(yield_sequence is (case.ego_policy == "yield"),
                "original yield/enter order differs from selected control")
    return {"case_id": ASSIGNMENT + "__" + case.name,
            "stop_reference": case.reference, "reference_station_m": reference,
            "stop_original_frame": stop["original_frame"],
            "entry_original_frame": entry["original_frame"],
            "stopped_at_required_position": position_ok,
            "priority_vehicle_observed": priority,
            "ego_policy": case.ego_policy,
            "other_clear_original_frame": other_clear_frame,
            "yield_sequence_observed": yield_sequence,
            "cautious_proceeding": None, "legal_judgment": None}
