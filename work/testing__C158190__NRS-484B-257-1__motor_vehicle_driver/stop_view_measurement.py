"""Original-frame measurements for a possible C158190 stop-sign allocation.

This is an unselected construction aid. Measurements preserve the stop and
through-traffic history without deciding right of way or immediate hazard.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from stop_sign_branch import ASSIGNMENT, CASES


SOURCE_KEYS = (
    "map_source_sha256",
    "ego_route_source_sha256",
    "stop_sign_survey_sha256",
    "marking_survey_sha256",
    "view_ray_survey_sha256",
    "through_highway_survey_sha256",
)


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + name + " required")
    return float(value)


def inspect_original(path: str | Path, case_id: str) -> dict:
    if case_id not in CASES:
        raise ValueError("unknown C158190 stop case")
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or packet.get("case_id") != case_id:
        raise ValueError("exact original stop case identity required")
    if not isinstance(packet.get("original_trace_id"), str) or not packet["original_trace_id"]:
        raise ValueError("original trace identity required")
    site = packet.get("site")
    if not isinstance(site, dict) or site.get("source_kind") != "original_native_readback":
        raise ValueError("original Native site readback required")
    if site.get("cell_id") != "C158190" or site.get("control") != "stop_sign":
        raise ValueError("fixed C158190 stop governance required")
    if site.get("planned_response") != CASES[case_id]:
        raise ValueError("planned stop response differs")
    if site.get("stop_line_present") is not False or site.get("near_crosswalk_present") is not False:
        raise ValueError("no-line and no-near-crosswalk survey required")
    if site.get("sidewalk_derived_crosswalk_present") is not False:
        raise ValueError("sidewalk-derived crosswalk survey required")
    if site.get("police_control_active") is not False or site.get("traffic_signal_control_active") is not False:
        raise ValueError("governing-control exception readback required")
    for key in SOURCE_KEYS:
        value = site.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("original source hash required: " + key)
    stations = site.get("approach_view_stations")
    if not isinstance(stations, list) or len(stations) < 2:
        raise ValueError("original nearest-view station survey required")
    visible = []
    station_ids = set()
    for station in stations:
        if not isinstance(station, dict) or not isinstance(station.get("station_id"), str):
            raise ValueError("original view station identity required")
        if not station["station_id"] or station["station_id"] in station_ids:
            raise ValueError("distinct view station identity required")
        station_ids.add(station["station_id"])
        distance = _number(station.get("distance_to_intersection_m"), "view distance")
        if distance < 0 or not isinstance(station.get("view_of_through_traffic"), bool):
            raise ValueError("original view station distance and visibility required")
        if station["view_of_through_traffic"]:
            visible.append((distance, station["station_id"]))
    if not visible:
        raise ValueError("no observed through-traffic view station")
    nearest_distance, nearest_id = min(visible)
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 900:
        raise ValueError("complete 900-frame original motion required")
    crossing = []
    stop_indices = []
    sightings = {}
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or frame.get("frame") != index:
            raise ValueError("consecutive original frame identity required")
        timestamp = _number(frame.get("time_s"), "frame time")
        if index and not 0.049 <= timestamp - _number(frames[index - 1].get("time_s"), "prior time") <= 0.051:
            raise ValueError("original 20 Hz time join required")
        speed = _number(frame.get("ego_speed_mps"), "ego speed")
        if speed < 0 or not isinstance(frame.get("ego_within_intersection"), bool):
            raise ValueError("original ego speed and occupancy required")
        if frame["ego_within_intersection"]:
            crossing.append(index)
        elif speed == 0:
            stop_indices.append(index)
        participants = frame.get("through_vehicles")
        if not isinstance(participants, list):
            raise ValueError("original through-highway history required at every frame")
        ids = set()
        for vehicle in participants:
            if not isinstance(vehicle, dict) or not isinstance(vehicle.get("id"), str) or not vehicle["id"]:
                raise ValueError("original through-vehicle identity required")
            if vehicle["id"] in ids or vehicle.get("through_highway") is not True:
                raise ValueError("distinct through-highway participant required")
            ids.add(vehicle["id"])
            distance = _number(vehicle.get("distance_to_conflict_m"), "through distance")
            through_speed = _number(vehicle.get("speed_mps"), "through speed")
            if through_speed < 0:
                raise ValueError("nonnegative through speed required")
            if frame["ego_within_intersection"]:
                sightings.setdefault(vehicle["id"], []).append((index, distance, through_speed))
    if not crossing or crossing != list(range(crossing[0], crossing[-1] + 1)):
        raise ValueError("contiguous original crossing required")
    if crossing[0] == 0 or crossing[-1] == len(frames) - 1:
        raise ValueError("entry and exit brackets required")
    before = [index for index in stop_indices if index < crossing[0]]
    if not before:
        raise ValueError("observed pre-entry stop sample required")
    return {
        "assignment_id": ASSIGNMENT,
        "case_id": case_id,
        "original_trace_id": packet["original_trace_id"],
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "nearest_sampled_visible_station_id": nearest_id,
        "nearest_sampled_visible_station_distance_m": nearest_distance,
        "pre_entry_stop_frame_indices": before,
        "crossing_frame_indices": [crossing[0], crossing[-1]],
        "through_vehicle_motion": [
            {"id": identity, "observed_crossing_frames": len(rows),
             "minimum_abs_distance_to_conflict_m": min(abs(row[1]) for row in rows),
             "speed_range_mps": [min(row[2] for row in rows), max(row[2] for row in rows)]}
            for identity, rows in sorted(sightings.items())
        ],
        "review_limit": "A zero-speed sample and sampled view station do not establish legal stopping location, immediate hazard, or right of way.",
    }


def compare_original(left: str | Path, right: str | Path) -> dict:
    left_packet = json.loads(Path(left).read_text())
    right_packet = json.loads(Path(right).read_text())
    expected = set(CASES)
    if {left_packet.get("case_id"), right_packet.get("case_id")} != expected:
        raise ValueError("exact stop-response pair required")
    left_result = inspect_original(left, left_packet["case_id"])
    right_result = inspect_original(right, right_packet["case_id"])
    fixed = SOURCE_KEYS + ("camera_plan_sha256", "intersection_id", "ego_route_id", "duration_frames")
    for key in fixed:
        first = left_packet["site"].get(key)
        if first is None or first != right_packet["site"].get(key):
            raise ValueError("fixed stop-response source differs: " + key)
    return {"assignment_id": ASSIGNMENT, "variable": "ego_response",
            "source_sha256": [left_result["source_sha256"], right_result["source_sha256"]],
            "measurements": [left_result, right_result],
            "review_limit": "Original motion comparison requires independent legal and physical review."}
