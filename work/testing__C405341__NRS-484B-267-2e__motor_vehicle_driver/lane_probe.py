"""Source-bound lane, motion and conditional-context measurement.

The output records original physical facts. It never decides whether a lane
change was legally possible or unsafe.
"""
from __future__ import annotations
from math import hypot
from emergency_construction import Case


def require(value, message):
    if not value:
        raise ValueError(message)


def measure(case: Case, site: dict, frames: list[dict]) -> dict:
    require(len(frames) == 900, "full original lane history required")
    require(site.get("source_kind") in ("reviewed_native_lane_site", "synthetic_lane_site"),
            "original lane site context required")
    for key in ("unit_lane_id", "adjacent_lane_id", "lane_adjacency_source",
                "target_authorization_source", "light_equipment_source"):
        require(isinstance(site.get(key), str) and site[key], key + " source missing")
    if case.condition != "roadway_impossible":
        require(site.get("nonadjacent_lane_id") and site.get("nonadjacent_route_connected") is True,
                "nonadjacent lane route source required")
        require(site.get("nonadjacent_lane_adjacent_to_unit") is False,
                "nonadjacent target lane remains adjacent to unit")
    else:
        require(site.get("nonadjacent_route_connected") is False and site.get("nonadjacent_route_absence_source"),
                "roadway impossibility source required")
    required = ("original_frame", "ego_xy", "emergency_xy", "ego_lane_id", "unit_lane_id",
                "flashing_light_on", "ego_speed_mps", "unit_speed_mps", "movement_visible",
                "driver_hand_signal_visible", "officer_direction", "traffic_path_occupied",
                "weather_adverse", "road_surface_state", "other_hazard_path_occupied", "approaching_unit",
                "lane_source", "motion_source", "light_source", "traffic_source",
                "weather_source", "other_hazard_source", "control_source")
    for row in frames:
        require(all(k in row for k in required), "original lane frame fields missing")
        require(row["unit_lane_id"] == site["unit_lane_id"], "unit lane identity changed")
        for key in ("lane_source", "motion_source", "light_source", "traffic_source",
                    "weather_source", "other_hazard_source", "control_source"):
            require(isinstance(row[key], str) and row[key], key + " original source missing")
    moving = [i for i in range(1, 900) if hypot(
        frames[i]["emergency_xy"][0] - frames[i-1]["emergency_xy"][0],
        frames[i]["emergency_xy"][1] - frames[i-1]["emergency_xy"][1]) > 0]
    if case.motion_state == "moving":
        require(moving and frames[0]["unit_speed_mps"] > 0,
                "original moving emergency unit required")
    elif case.motion_state == "preparing_movement":
        require(any(row["movement_visible"] for row in frames) and moving,
                "visible original movement preparation cue required")
    else:
        require(any(row["driver_hand_signal_visible"] and row.get("hand_signal_source")
                    for row in frames), "visible original driver hand signal required")
    if case.qualifying_lights:
        require(any(row["flashing_light_on"] for row in frames),
                "original qualifying flashing light use required")
    else:
        require(not any(row["flashing_light_on"] for row in frames),
                "inactive-light case contains original flash use")
    if case.approaching:
        require(any(row["approaching_unit"] for row in frames),
                "actual original ego approach required")
    else:
        require(not any(row["approaching_unit"] for row in frames),
                "nonapproach case contains actual approach")
    if case.officer_direction:
        require(site.get("law_enforcement_officer_source") and
                any(row["officer_direction"] for row in frames),
                "original law-enforcement officer direction required")
    if case.condition == "traffic_unsafe":
        require(any(row["traffic_path_occupied"] for row in frames),
                "original nonadjacent traffic path occupation required")
        require(site.get("traffic_trajectory_source"), "traffic trajectory source missing")
    if case.condition == "other_hazard":
        require(site.get("other_hazard_kind") == "fallen_cargo" and
                site.get("other_hazard_geometry_source") and
                any(row["other_hazard_path_occupied"] for row in frames),
                "original other-hazard geometry/path occupation required")
    if case.condition == "weather_unsafe":
        require(any(row["weather_adverse"] for row in frames) and
                site.get("weather_readback_source") and site.get("road_surface_source"),
                "original weather and road surface sources required")
    chosen = site["nonadjacent_lane_id"] if case.lane_choice == "nonadjacent" else site["adjacent_lane_id"]
    require(any(row["ego_lane_id"] == chosen for row in frames[350:800]),
            "requested lane never appears in original ego lane history")
    return {
        "unit_displacement_m": hypot(frames[-1]["emergency_xy"][0] - frames[0]["emergency_xy"][0],
                                     frames[-1]["emergency_xy"][1] - frames[0]["emergency_xy"][1]),
        "ego_lane_original_frames": {lane: [row["original_frame"] for row in frames if row["ego_lane_id"] == lane]
                                     for lane in {row["ego_lane_id"] for row in frames}},
        "unit_lane_id": site["unit_lane_id"],
        "nonadjacent_route_connected": site["nonadjacent_route_connected"],
        "traffic_occupied_original_frames": [row["original_frame"] for row in frames if row["traffic_path_occupied"]],
        "other_hazard_original_frames": [row["original_frame"] for row in frames if row["other_hazard_path_occupied"]],
        "weather_adverse_original_frames": [row["original_frame"] for row in frames if row["weather_adverse"]],
        "preparation_cue_original_frames": [row["original_frame"] for row in frames if row["movement_visible"] or row["driver_hand_signal_visible"]],
        "officer_direction_original_frames": [row["original_frame"] for row in frames if row["officer_direction"]],
        "legal_possible_and_safe": "unresolved",
    }
