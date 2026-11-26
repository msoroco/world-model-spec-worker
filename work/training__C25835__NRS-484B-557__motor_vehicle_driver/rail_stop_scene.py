"""Authored CARLA construction request for the C25835 blind rail crossing.

Native map/prop readback and source pixels must be checked during a later run.
An authored stop-sign prop is not proof of official designation or governance.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from rail_stop_controller import STOP_CENTER_DISTANCE_FT, FEET_PER_METRE


ROAD_ID = 25835
ROAD_START_X_M = -100.0
ROAD_LENGTH_M = 200.0
LANE_WIDTH_M = 3.5
NEAREST_TRACK_X_M = 0.0
FAR_TRACK_X_M = 1.5
APPROACH_Y_M = -LANE_WIDTH_M / 2
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C25835-blind-rail-crossing-request", version="1",
                  north="15", south="-15", east="100", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C25835_rail_approach",
                         length=str(ROAD_LENGTH_M), junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(ROAD_START_X_M), y="0", hdg="0",
                             length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, ident in (("left", 1), ("center", 0), ("right", -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", id=str(ident),
                             type="none" if ident == 0 else "driving", level="false")
        if ident:
            ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                          b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0",
                      type="solid" if ident == 0 else "broken",
                      color="yellow" if ident == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, vehicle_blueprint="vehicle.tesla.model3",
                  rail_blueprint="static.prop.ironplank",
                  stop_sign_blueprint="static.prop.stop",
                  occluder_blueprint="static.prop.hedge"):
    if case not in STOP_CENTER_DISTANCE_FT:
        raise ValueError("Unknown rail-stop comparison case")
    for name, value in (("vehicle", vehicle_blueprint), ("rail", rail_blueprint),
                        ("stop sign", stop_sign_blueprint), ("occluder", occluder_blueprint)):
        prefix = "vehicle." if name == "vehicle" else "static.prop."
        if not isinstance(value, str) or not value.startswith(prefix):
            raise ValueError(f"Invalid {name} blueprint request")
    stop_x = NEAREST_TRACK_X_M - STOP_CENTER_DISTANCE_FT[case] / FEET_PER_METRE
    if not ROAD_START_X_M < -65 < stop_x < NEAREST_TRACK_X_M < FAR_TRACK_X_M < ROAD_START_X_M + ROAD_LENGTH_M:
        raise ValueError("Rail stop route geometry invalid")
    return {
        "format": "worker-authored-blind-rail-scene-request",
        "case": case, "road_id": ROAD_ID,
        "road_opendrive": open_drive(),
        "vehicle": {"blueprint": vehicle_blueprint, "start_xyz": [-65, APPROACH_Y_M, 0.5],
                    "heading_deg": 0, "requested_stop_center_x_m": stop_x},
        "rails": {"blueprint": rail_blueprint,
                  "nearest_track_x_m": NEAREST_TRACK_X_M,
                  "far_track_x_m": FAR_TRACK_X_M,
                  "physical_railroad_status_verified": False},
        "stop_sign": {"blueprint": stop_sign_blueprint,
                      "xyz": [-19.5, -4.5, 0], "heading_deg": 0,
                      "official_governance_verified": False},
        "occluder": {"blueprint": occluder_blueprint,
                     "xyz": [-4, 6, 0], "heading_deg": 90,
                     "visibility_effect_verified": False},
        "cameras": [
            {"name": "overview", "xyz": [-18, -13, 25], "yaw": 35, "pitch": -50, "size": [1920, 1080]},
            {"name": "approach", "xyz": [-30, -11, 10], "yaw": 0, "pitch": -20, "size": [1280, 720]},
            {"name": "reference_corner", "xyz": [1, -12, 8], "yaw": 90, "pitch": -20, "size": [1280, 720]},
            {"name": "driver_reference", "xyz": [5, 12, 8], "yaw": 180, "pitch": -20, "size": [1280, 720]},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "designation_record_source_required": True,
        "physical_success_claimed": False,
    }


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != str(ROAD_ID):
        raise ValueError("Authored road identity missing")
    lanes = road.findall("lanes/laneSection/*/lane")
    if {lane.attrib["id"] for lane in lanes} != {"-1", "0", "1"}:
        raise ValueError("Two-way driving lanes missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if {camera["name"] for camera in request.get("cameras", [])} != set(CAMERAS):
        raise ValueError("Four source-camera requests missing")
    if request["stop_sign"]["official_governance_verified"] or request["rails"]["physical_railroad_status_verified"]:
        raise ValueError("Authored request cannot assert Native or administrative verification")
    return {"case": request["case"], "road_id": ROAD_ID,
            "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_geometry_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in STOP_CENTER_DISTANCE_FT}, indent=2))
