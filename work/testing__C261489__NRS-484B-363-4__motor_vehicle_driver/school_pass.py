"""Source-gated same-direction school-zone pass construction and original measurement."""

from __future__ import annotations

from math import isfinite
from typing import Mapping

from school_timing import derive as derive_timing


ASSIGNMENT = "testing__C261489__NRS-484B-363-4__motor_vehicle_driver"
CASES = (
    "active_beacon_pass", "school_not_in_session", "after_end_29m", "after_end_30m",
    "after_end_31m", "before_start_31m", "before_start_30m", "before_start_29m",
    "class_no_flash", "sign_without_operational_beacon", "no_pass", "outside_zone",
)
SOURCES = (
    "driver_identity", "ego_vehicle_class", "target_vehicle_class", "zone_designation",
    "zone_extent", "school_property", "map_geometry", "ego_route", "target_route",
    "school_calendar", "operation_schedule", "class_schedule", "local_clock",
    "beacon_configuration", "beacon_state", "sign_instruction",
)


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def point(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def polygon(value: object) -> bool:
    return isinstance(value, list) and len(value) >= 3 and all(point(p) for p in value)


def inside(point_xy: object, vertices: list) -> bool:
    if not point(point_xy) or not polygon(vertices):
        return False
    x, y = point_xy
    crossing = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if (a[1] > y) != (b[1] > y):
            edge_x = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
            if x < edge_x:
                crossing = not crossing
    return crossing


def case_name(case_id: str) -> str:
    require(case_id.startswith(ASSIGNMENT + "__"), "exact assignment case required")
    name = case_id[len(ASSIGNMENT) + 2:]
    require(name in CASES, "unknown exact school pass case")
    return name


def validate_scene(scene: Mapping, case_id: str) -> dict:
    name = case_name(case_id)
    require(scene.get("case_id") == case_id and scene.get("cell_id") == "C261489" and
            scene.get("actor") == "motor_vehicle_driver" and scene.get("law_id") == "NRS-484B-363-4",
            "school pass scope differs")
    require(scene.get("driver_id") and scene.get("ego_id") and scene.get("target_id") and
            scene["ego_id"] != scene["target_id"], "two original vehicle identities required")
    require(scene.get("ego_vehicle_class") == "conventional_motor_vehicle" and
            scene.get("target_vehicle_class") == "conventional_motor_vehicle",
            "conventional motor vehicle classes required")
    require(scene.get("same_direction") is True, "same-direction vehicles required")
    require(polygon(scene.get("designated_zone_polygon_xy")) and
            polygon(scene.get("school_property_polygon_xy")) and
            scene.get("zone_designation_kind") in ("school_zone", "school_crossing_zone"),
            "physical school-zone designation/geometry missing")
    require(scene.get("school_property_adjacency_reviewed") is True,
            "school property adjacency review required")
    for route in ("ego_route_xy", "target_route_xy"):
        value = scene.get(route)
        require(isinstance(value, list) and len(value) >= 3 and all(point(p) for p in value),
                "physical lane-connected route required: " + route)
    require(scene.get("ego_route_lane_ids") and scene.get("target_route_lane_ids") and
            len(scene["ego_route_lane_ids"]) == len(scene["ego_route_xy"]) and
            len(scene["target_route_lane_ids"]) == len(scene["target_route_xy"]),
            "source-reviewed lane direction/route missing")
    require(scene.get("passing_lane_direction") == "same_as_ego" and
            scene.get("target_lane_direction") == "same_as_ego",
            "passing and target lanes must have surveyed same travel direction")
    route_inside = [inside(p, scene["designated_zone_polygon_xy"]) for p in scene["ego_route_xy"]]
    if name == "outside_zone":
        require(not any(route_inside), "outside-zone physical route remains in designated zone")
    else:
        require(all(route_inside), "physical pass route leaves designated school zone")
    require(type(scene.get("pass_start_frame")) is int and
            type(scene.get("pass_end_frame")) is int and
            0 <= scene["pass_start_frame"] < scene["pass_end_frame"] < 900,
            "original pass interval missing")
    for source in SOURCES:
        value = scene.get(source + "_source_sha256")
        require(isinstance(value, str) and len(value) == 64 and
                all(char in "0123456789abcdef" for char in value),
                "source-hashed original context missing: " + source)
    facts = derive_timing(scene.get("timing_packet"))
    require(scene.get("local_datetime") == scene["timing_packet"]["local_datetime"],
            "local clock differs from independent timing packet")
    if name == "school_not_in_session":
        require(facts["school_in_session"] is False, "no-session calendar source required")
    if name.startswith("after_end_"):
        require(facts["after_end_minutes"] == int(name.split("_")[-1][:-1]),
                "after-end exact clock probe differs")
    if name.startswith("before_start_"):
        require(facts["before_start_minutes"] == int(name.split("_")[-1][:-1]),
                "before-start exact clock probe differs")
    if name == "class_no_flash":
        require(facts["during_pupil_class_hours"] and
                facts["zone_designated_by_operational_beacon"] and
                not facts["alternating_flash_observed"],
                "class-hour no-flash source condition differs")
    elif name == "sign_without_operational_beacon":
        require(not facts["zone_designated_by_operational_beacon"] and
                not facts["sign_limit_active"],
                "sign-only inactive-limit source condition differs")
    else:
        require(facts["zone_designated_by_operational_beacon"] and
                facts["alternating_flash_observed"],
                "operational flashing beacon baseline missing")
    require(scene.get("pass_requested") is (name != "no_pass"),
            "pass request differs from exact case")
    return {"case_id": case_id, "timing": facts, "legal_judgment": None}


def construct(adapter, scene: Mapping, case_id: str) -> dict:
    """Request two vehicles and a lane-changing pass; keep owned resources local."""
    context = validate_scene(scene, case_id)
    owned = []
    try:
        ego = adapter.spawn_vehicle(scene["ego_id"], scene["ego_route_xy"][0],
                                    scene["ego_vehicle_class"])
        require(ego is not None, "ego spawn failed")
        owned.append(ego)
        target = adapter.spawn_vehicle(scene["target_id"], scene["target_route_xy"][0],
                                       scene["target_vehicle_class"])
        require(target is not None, "target spawn failed")
        owned.append(target)
        adapter.set_route(ego, scene["ego_route_xy"], scene["ego_route_lane_ids"])
        adapter.set_route(target, scene["target_route_xy"], scene["target_route_lane_ids"])
        adapter.set_pass_window(ego, target, scene["pass_start_frame"],
                                scene["pass_end_frame"], scene["pass_requested"])
        adapter.set_beacon(context["timing"]["beacon_operational"],
                           context["timing"]["alternating_flash_observed"])
        readback = adapter.read_beacon()
        require(isinstance(readback, dict) and
                readback.get("operational") is context["timing"]["beacon_operational"] and
                readback.get("alternating_flash") is context["timing"]["alternating_flash_observed"],
                "Native beacon readback differs")
        return {"owned": tuple(owned), **context}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], scene: Mapping, case_id: str) -> dict:
    """Measure physical pass from 900 original frames; never infer it from command."""
    validate_scene(scene, case_id)
    require(len(rows) == 900, "original 900-frame capture missing")
    start_frame = rows[0].get("original_frame")
    t0 = rows[0].get("time_s")
    require(type(start_frame) is int and number(t0), "original frame/time missing")
    progress = []
    inside_frames = 0
    lateral_crossing = False
    for index, row in enumerate(rows):
        require(row.get("original_frame") == start_frame + index and
                number(row.get("time_s")) and abs(row["time_s"] - t0 - index / 20) <= .005,
                "original frame/time join invalid")
        require(row.get("ego_id") == scene["ego_id"] and row.get("target_id") == scene["target_id"] and
                row.get("driver_id") == scene["driver_id"], "original vehicle/driver identity changed")
        for source in SOURCES:
            require(row.get(source + "_source_sha256") == scene[source + "_source_sha256"],
                    "original source changed: " + source)
        for field in ("ego_xy", "target_xy"):
            require(point(row.get(field)), "original vehicle body location missing: " + field)
        for field in ("ego_route_progress_m", "target_route_progress_m", "lateral_separation_m"):
            require(number(row.get(field)), "original physical trajectory metric missing: " + field)
        if scene["pass_start_frame"] <= index <= scene["pass_end_frame"]:
            progress.append(row["ego_route_progress_m"] - row["target_route_progress_m"])
            if inside(row["ego_xy"], scene["designated_zone_polygon_xy"]) and inside(row["target_xy"], scene["designated_zone_polygon_xy"]):
                inside_frames += 1
            if row["lateral_separation_m"] >= scene.get("minimum_lateral_clearance_m", 1.0):
                lateral_crossing = True
    require(progress, "original pass interval empty")
    completed = progress[0] < 0 and progress[-1] > 0 and lateral_crossing
    zone_pass = inside_frames == len(progress)
    name = case_name(case_id)
    if name == "no_pass":
        require(not completed, "no-pass reference actually passed target")
    else:
        require(completed, "same-direction overtake and pass not physically completed")
    if name == "outside_zone":
        require(not zone_pass, "outside-zone pass remained inside designated zone")
    elif name != "no_pass":
        require(zone_pass, "pass left designated school zone")
    return {"case_id": case_id, "completed_pass": completed,
            "pass_inside_zone": zone_pass, "pass_frames": len(progress),
            "first_relative_progress_m": progress[0], "last_relative_progress_m": progress[-1],
            "lateral_clearance_observed": lateral_crossing, "legal_judgment": None}
