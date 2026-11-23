"""Portable exact green-arrow scene checks for materialized bundles."""
from __future__ import annotations

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


KINDS = ("green_selected_drive", "adjacent_dark_drive", "second_green_drive",
         "green_selected_stand")
LANES = {"east": (-1, -1.8, [-3.6, 0.0]), "west": (-2, -5.4, [-7.2, -3.6])}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_road(path):
    root = ET.parse(path).getroot()
    roads = root.findall("road")
    if len(roads) != 1 or roads[0].get("id") != "147332" or float(roads[0].get("length", 0)) != 90:
        raise ValueError("wrong exact one-way road")
    sections = roads[0].findall("./lanes/laneSection")
    if len(sections) != 1:
        raise ValueError("one lane section required")
    lanes = sections[0].findall("./right/lane")
    if {int(lane.get("id")) for lane in lanes} != {-1, -2} or any(
            lane.get("type") != "driving" or float(lane.find("width").get("a")) != 3.6
            for lane in lanes):
        raise ValueError("two 3.6 m same-direction driving lanes required")
    if sections[0].findall("./left/lane"):
        raise ValueError("counterflow lane in one-way scene")
    return {"road_sha256": sha(path), "lane_ids": [-1, -2], "native_import_verified": False}


def check_scene(scene, road):
    kind = scene.get("case_id", "").removeprefix(scene.get("assignment_id", "") + "__")
    if kind not in KINDS or scene.get("law_id") != "NRS-484B-307-12a" or scene.get("cell_id") != "C147332":
        raise ValueError("unexpected exact green-arrow case")
    source = check_road(road)
    if scene.get("map_source") != "road.xodr" or scene.get("map_source_sha256") != source["road_sha256"]:
        raise ValueError("scene map source changed")
    lane = "west" if kind in ("adjacent_dark_drive", "second_green_drive") else "east"
    if scene.get("bus_lane_id") != lane or scene.get("bus_blueprint_id") != "vehicle.mitsubishi.fusorosa":
        raise ValueError("exact bus identity/lane changed")
    expected_x = [8.0] * 3 if kind == "green_selected_stand" else [8.0, 45.0, 82.0]
    if scene.get("route_waypoint_centers_m") != [[x, LANES[lane][1]] for x in expected_x]:
        raise ValueError("exact route request changed")
    expected_green = {"east", "west"} if kind == "second_green_drive" else {"east"}
    signals = scene.get("signals")
    if not isinstance(signals, list) or len(signals) != 2:
        raise ValueError("one head above each lane required")
    for signal in signals:
        key = signal.get("governed_lane_id")
        if key not in LANES:
            raise ValueError("unexpected governed lane")
        road_lane, center, bounds = LANES[key]
        if (signal.get("road_lane_id") != road_lane or signal.get("lateral_bounds_m") != bounds or
                signal.get("longitudinal_m") != 50.0 or signal.get("lateral_m") != center or
                signal.get("height_m", 0) < 5.0 or signal.get("placement") != "over_individual_lanes" or
                signal.get("facing") != "bus_approach" or
                signal.get("display") != ("down_green_arrow" if key in expected_green else "dark")):
            raise ValueError("overhead signal placement/state changed")
    if {signal["governed_lane_id"] for signal in signals} != set(LANES):
        raise ValueError("duplicate or missing lane head")
    if scene.get("capture_plan") != {"rate_hz": 20, "duration_s": 18,
                                     "cameras": ["overview", "approach", "reference_corner", "driver_reference"]}:
        raise ValueError("four-camera duration plan changed")
    return {"case_id": scene["case_id"], "road": source,
            "bus_route_target_checked": True, "signal_geometry_target_checked": True,
            "official_device_reviewed": False, "native_motion_verified": False}
