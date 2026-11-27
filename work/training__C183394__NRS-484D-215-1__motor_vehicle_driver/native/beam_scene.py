"""CPU-authored shoulder and opposed-vehicle lighting comparison request.

The road, actors, lamp bits and camera mounts are requests. Original Native map
readback, emitted beam optics, driver-eye exposure and legal outcome remain open.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

from oncoming_beam import FIVE_HUNDRED_FEET_M


ROAD_ID = 183394
START_X_M = -250.0
ROAD_LENGTH_M = 500.0
LANE_WIDTH_M = 3.5
SHOULDER_WIDTH_M = 3.0
EGO_Y_M = -(LANE_WIDTH_M + SHOULDER_WIDTH_M / 2)
ONCOMING_Y_M = LANE_WIDTH_M / 2
MODES = {"condition_a": "dim_within_500", "condition_b": "retain_high"}
CAMERAS = ("overview", "ego_forward", "oncoming_eye", "beam_reference")


def road_opendrive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C183394-shoulder",
                  version="1", north="10", south="-10", east="250", west="-250",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C183394_paved_shoulder",
                         length=str(ROAD_LENGTH_M), junction="-1")
    ET.SubElement(road, "link")
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0",
                         x=str(START_X_M), y="0", hdg="0", length=str(ROAD_LENGTH_M))
    ET.SubElement(geom, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, specs in (("left", ((1, "driving", LANE_WIDTH_M),)),
                        ("center", ((0, "none", 0),)),
                        ("right", ((-1, "driving", LANE_WIDTH_M),
                                   (-2, "shoulder", SHOULDER_WIDTH_M)))):
        group = ET.SubElement(section, side)
        for ident, lane_type, width in specs:
            lane = ET.SubElement(group, "lane", id=str(ident), type=lane_type, level="false")
            if width:
                ET.SubElement(lane, "width", sOffset="0", a=str(width), b="0", c="0", d="0")
            ET.SubElement(lane, "roadMark", sOffset="0",
                          type="solid" if ident in (0, -2) else "broken",
                          color="yellow" if ident == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def beam_request(mode, separation_m):
    if mode not in MODES.values():
        raise ValueError("unknown beam comparison mode")
    if isinstance(separation_m, bool) or not isinstance(separation_m, (int, float)) \
            or not math.isfinite(separation_m) or separation_m < 0:
        raise ValueError("measured oncoming separation required")
    if mode == "retain_high":
        return "high_beam"
    return "low_beam" if separation_m <= FIVE_HUNDRED_FEET_M else "high_beam"


def request(case):
    if case not in MODES:
        raise ValueError("unknown lighting comparison case")
    return {
        "format": "worker-authored-shoulder-oncoming-beam-request",
        "cell_id": "C183394", "case": case, "beam_mode": MODES[case],
        "road_opendrive": road_opendrive(), "road_id": ROAD_ID,
        "ego": {"blueprint": "vehicle.carlamotors.carlacola",
                "start_xyz_m": [-100, EGO_Y_M, 1.2], "heading_deg": 0,
                "target_lane_id": -2, "road_position_claim": "requested_adjacent_shoulder"},
        "oncoming": {"blueprint": "vehicle.audi.tt", "start_xyz_m": [100, ONCOMING_Y_M, 1.2],
                       "heading_deg": 180, "target_lane_id": 1,
                       "driver_eye_region": "original pixel review required"},
        "lighting": {"weather_request": "ClearNight", "trigger_source": "NRS-484D-100-1",
                     "trigger_evidence": "original clock or visibility source required",
                     "lowermost_distribution_claimed": False,
                     "emitted_glare_claimed": False},
        "cameras": [
            {"name": "overview", "xyz_m": [0, -18, 25], "yaw_deg": 0, "pitch_deg": -55,
             "size": [1920, 1080], "mount": "world"},
            {"name": "ego_forward", "xyz_m": [1, 0, 2], "yaw_deg": 0, "pitch_deg": -8,
             "size": [1280, 720], "mount": "ego"},
            {"name": "oncoming_eye", "xyz_m": [0.4, 0, 1.4], "yaw_deg": 0,
             "pitch_deg": 0, "size": [1280, 720], "mount": "oncoming"},
            {"name": "beam_reference", "xyz_m": [0, -9, 5], "yaw_deg": 0,
             "pitch_deg": -12, "size": [1280, 720], "mount": "world"},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "physical_success_claimed": False,
    }


def validate_request(plan):
    road = ET.fromstring(plan["road_opendrive"]).find("road")
    if road is None or road.attrib.get("id") != str(ROAD_ID):
        raise ValueError("authored road identity missing")
    lanes = {(int(l.attrib["id"]), l.attrib["type"])
             for l in road.findall("lanes/laneSection/*/lane")}
    if lanes != {(1, "driving"), (0, "none"), (-1, "driving"), (-2, "shoulder")}:
        raise ValueError("adjacent shoulder and opposed driving lanes required")
    if plan["ego"]["target_lane_id"] != -2 or plan["oncoming"]["target_lane_id"] != 1:
        raise ValueError("shoulder and oncoming lane targets required")
    if plan["ego"]["heading_deg"] != 0 or plan["oncoming"]["heading_deg"] != 180:
        raise ValueError("opposed travel requests required")
    if {c["name"] for c in plan.get("cameras", ())} != set(CAMERAS):
        raise ValueError("four distinct camera requests required")
    if plan.get("rate_hz") != 20 or plan.get("planned_frames") != 600:
        raise ValueError("30-second 20 Hz capture required")
    if plan["lighting"]["lowermost_distribution_claimed"] or \
            plan["lighting"]["emitted_glare_claimed"] or plan["physical_success_claimed"]:
        raise ValueError("authored request cannot claim physical or legal result")
    return {"case": plan["case"], "road_id": ROAD_ID, "camera_count": 4,
            "frames": 600, "physical_verified": False}
