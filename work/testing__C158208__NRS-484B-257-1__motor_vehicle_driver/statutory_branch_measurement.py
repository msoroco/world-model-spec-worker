"""Measure reference and through-traffic history for all 257(1) yield cases.

This produces engineering observations only. It does not infer an immediate
hazard, legal stopping sufficiency or a right-of-way conclusion.
"""
from __future__ import annotations

import math

from branch_site_preflight import validate_site_branch
from source_tick_capture import validate_geometry


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be a finite number")
    return float(value)


def measure_branch(packet: dict, site: dict, case_id: str) -> dict:
    planned = validate_site_branch(site, case_id)
    geometry = packet.get("geometry")
    _, _, through_origin, through_axis, _, polygon = validate_geometry(geometry)
    if packet.get("reviewed_context") != site.get("reviewed_context"):
        raise ValueError("original tick context differs from reviewed site")
    reference = _finite(site.get("stopping_reference_station_m"),
                        "reviewed stopping reference station")
    through_stations = [(x - through_origin[0]) * through_axis[0] +
                        (y - through_origin[1]) * through_axis[1] for x, y in polygon]
    through_near, through_far = min(through_stations), max(through_stations)
    samples = packet.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        raise ValueError("original tick history needs at least three samples")
    observations = []
    prior_time = -math.inf
    first_reference = None
    first_ego_entry = None
    first_through_entry = None
    for index, sample in enumerate(samples):
        time_s = _finite(sample.get("time_s"), "original time")
        if time_s <= prior_time:
            raise ValueError("original tick time must increase")
        prior_time = time_s
        speed = _finite(sample.get("ego_speed_mps"), "ego speed")
        ego_station = _finite(sample.get("ego_front_station_m"), "ego front station")
        through_station = _finite(sample.get("through_center_station_m"),
                                  "through center station")
        occupied = sample.get("through_vehicle_within_intersection")
        entered = sample.get("intersection_entry")
        visible = sample.get("through_traffic_visible")
        if speed < 0 or not all(isinstance(v, bool) for v in (occupied, entered, visible)):
            raise ValueError("original speed or boolean observation invalid")
        if first_reference is None and ego_station >= reference:
            first_reference = index
        if first_ego_entry is None and entered:
            first_ego_entry = index
        if first_through_entry is None and occupied:
            first_through_entry = index
        observations.append({"frame": sample["frame"], "time_s": time_s,
                             "ego_front_station_m": ego_station, "ego_speed_mps": speed,
                             "through_center_station_m": through_station,
                             "through_within_intersection": occupied,
                             "through_approaching_intersection": through_station < through_near,
                             "ego_within_or_across_intersection": entered,
                             "through_visible": visible})
    if first_reference is None or first_ego_entry is None:
        raise ValueError("original ego never reaches reference or intersection")
    if first_reference > first_ego_entry:
        raise ValueError("stopping reference lies beyond observed intersection entry")
    approach = observations[:first_reference + 1]
    crossing = observations[first_ego_entry:]
    return {"case_id": case_id, "reference_branch": planned["reference_branch"],
            "reference_station_m": reference,
            "reference_crossing_frame": observations[first_reference]["frame"],
            "ego_entry_frame": observations[first_ego_entry]["frame"],
            "first_through_occupancy_frame": None if first_through_entry is None else observations[first_through_entry]["frame"],
            "through_intersection_station_interval_m": [through_near, through_far],
            "minimum_approach_speed_mps": min(row["ego_speed_mps"] for row in approach),
            "through_occupied_during_ego_crossing": any(row["through_within_intersection"] for row in crossing),
            "through_approaching_before_ego_entry": any(row["through_approaching_intersection"] for row in observations[:first_ego_entry]),
            "planned_through_traffic_phase": planned["planned_through_traffic_phase"],
            "observed_history": observations,
            "legal_status": "unresolved"}
