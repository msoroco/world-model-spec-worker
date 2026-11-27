"""Source-hashed original activity measurements for LVMC 11.20.060.

Results are physical observations. They do not set statutory meanings for
"immediately prior", pedestrian necessity, or roadway right-of-way.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from driveway_construction import _inside, _polygon, _xy

SOURCES = ("frame_map", "driveway_geometry", "activity")


def load_sources(root, *, diagnostic=False):
    root = Path(root)
    inventory_path = root / "inventory.json"
    if not inventory_path.is_file():
        raise ValueError("Missing required source: inventory.json")
    inventory = json.loads(inventory_path.read_text())
    expected_kind = "synthetic_fixture" if diagnostic else "original_native"
    if inventory.get("source_kind") != expected_kind or inventory.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("original Native source provenance differs")
    loaded = {}
    for name in SOURCES:
        entry = inventory.get("sources", {}).get(name)
        if not isinstance(entry, dict) or entry.get("path") != name + ".json":
            raise ValueError("Missing required source: " + name)
        path = root / entry["path"]
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
            raise ValueError("original source hash changed: " + name)
        loaded[name] = json.loads(path.read_text())
    return inventory, loaded


def measure(root, case, *, diagnostic=False):
    inventory, source = load_sources(root, diagnostic=diagnostic)
    case_id = case["case_id"]
    if inventory.get("case_id") != case_id:
        raise ValueError("source exact case differs")
    geo = source["driveway_geometry"]
    if geo.get("case_id") != case_id or geo.get("source_kind") != (
            "synthetic_fixture" if diagnostic else "original_native_geometry"):
        raise ValueError("driveway geometry source differs")
    for key in ("district_source", "frontage_source", "private_driveway_source",
                "sidewalk_source", "roadway_source", "connection_source"):
        if not geo.get(key):
            raise ValueError("original context source absent: " + key)
    if geo.get("district") != "residence" or geo.get("business_district") is not False:
        raise ValueError("residence district unverified")
    if geo.get("access") != "private_driveway" or geo.get("road_connection") is not True:
        raise ValueError("driveway road connection unverified")
    sidewalk = _polygon(geo.get("sidewalk_polygon_m"), "sidewalk")
    roadway = _polygon(geo.get("roadway_polygon_m"), "roadway")
    frame_map = source["frame_map"].get("frames", [])
    activity = source["activity"].get("samples", [])
    expected = 9 if diagnostic else 900
    if len(frame_map) != expected or len(activity) != expected:
        raise ValueError("original frame/activity length incomplete")
    ego, pedestrians, roadway_vehicles = [], [], []
    for i, (frame, sample) in enumerate(zip(frame_map, activity)):
        if (frame.get("video_frame") != i or type(frame.get("frame")) is not int or
                type(frame.get("time_s")) not in (int, float) or
                sample.get("frame") != frame["frame"] or
                sample.get("time_s") != frame["time_s"]):
            raise ValueError("original frame identity/time join differs")
        if i and (frame["frame"] != frame_map[i - 1]["frame"] + 1 or
                  abs(frame["time_s"] - frame_map[i - 1]["time_s"] - .05) > .001):
            raise ValueError("original frame gap or cadence drift")
        e = sample.get("ego")
        if not isinstance(e, dict) or e.get("actor_id") != geo.get("ego_vehicle_id"):
            raise ValueError("original ego actor source missing")
        point = _xy(e.get("xy_m"), "ego")
        speed = e.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original ego speed missing")
        ego.append({"frame": frame["frame"], "time_s": frame["time_s"],
                    "xy_m": point, "speed_mps": float(speed),
                    "on_sidewalk": _inside(point, sidewalk),
                    "on_roadway": _inside(point, roadway)})
        pedestrians.append(sample.get("pedestrian"))
        roadway_vehicles.append(sample.get("roadway_vehicle"))
    sidewalk_entry = next((i for i, e in enumerate(ego) if e["on_sidewalk"]), None)
    road_entry = next((i for i, e in enumerate(ego) if e["on_roadway"]), None)
    if sidewalk_entry is None or road_entry is None or not sidewalk_entry < road_entry:
        raise ValueError("original sidewalk-to-roadway crossing not observed")
    prior_halts = [e for e in ego[:sidewalk_entry] if e["speed_mps"] <= .08]
    halt = prior_halts[-1] if prior_halts else None
    ped_mode = case["world_setup"]["pedestrian"]
    if ped_mode != "pedestrian_absent":
        for i, p in enumerate(pedestrians):
            if not isinstance(p, dict) or not p.get("actor_id") or not p.get("source"):
                raise ValueError("original pedestrian activity source missing")
            _xy(p.get("xy_m"), "pedestrian")
    elif any(p is not None for p in pedestrians):
        raise ValueError("unexpected pedestrian in fixed absent condition")
    road_mode = case["world_setup"]["roadway_vehicle"]
    if road_mode != "roadway_clear":
        direction = "left" if road_mode.startswith("left_") else "right"
        for v in roadway_vehicles:
            if (not isinstance(v, dict) or not v.get("actor_id") or
                    not v.get("source") or v.get("approach_direction") != direction):
                raise ValueError("original roadway vehicle activity source missing")
            _xy(v.get("xy_m"), "roadway vehicle")
    elif any(v is not None for v in roadway_vehicles):
        raise ValueError("unexpected roadway vehicle in fixed clear condition")
    ped_separation = ([math.dist(e["xy_m"], _xy(p["xy_m"], "pedestrian"))
                       for e, p in zip(ego, pedestrians) if p is not None] or [None])
    vehicle_separation = ([math.dist(e["xy_m"], _xy(v["xy_m"], "roadway vehicle"))
                           for e, v in zip(ego, roadway_vehicles) if v is not None] or [None])
    return {
        "case_id": case_id,
        "source_kind": inventory["source_kind"],
        "frame_count": expected,
        "first_sidewalk_frame": ego[sidewalk_entry]["frame"],
        "first_roadway_frame": ego[road_entry]["frame"],
        "last_pre_sidewalk_halt_frame": halt["frame"] if halt else None,
        "last_pre_sidewalk_halt_xy_m": list(halt["xy_m"]) if halt else None,
        "pre_sidewalk_speed_mps": ego[sidewalk_entry - 1]["speed_mps"],
        "minimum_pedestrian_center_separation_m": min(ped_separation) if ped_separation[0] is not None else None,
        "minimum_roadway_vehicle_center_separation_m": min(vehicle_separation) if vehicle_separation[0] is not None else None,
        "pedestrian_source_present": ped_mode != "pedestrian_absent",
        "roadway_vehicle_source_present": road_mode != "roadway_clear",
        "statutory_stop_judgment": None,
        "pedestrian_collision_necessity_judgment": None,
        "roadway_right_of_way_judgment": None,
        "source_sha256": {name: inventory["sources"][name]["sha256"] for name in SOURCES},
    }
