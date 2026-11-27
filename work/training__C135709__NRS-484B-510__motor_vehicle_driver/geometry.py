"""Prospective narrow-road restricted parking zone for four exact cases.

The authored sign requests a purpose; official authority, effective conditions,
legibility and actual zone boundaries require original source review.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

ROAD_ID = 1
SIGN_ID = "510"
SIGN_NAME = "RESTRICTED PARKING TEST PURPOSE"
RESTRICTED_PURPOSE = "test_purpose"
ZONE_X_M = (0.0, 10.0)
ZONE_Y_M = (-4.0, -1.0)


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C135709-zone",
                  version="1", date="2026-11-26", north="8", south="-8",
                  east="70", west="-70", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="narrow-road",
                         length="140", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-70", y="0", hdg="0", length="140")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none",
                  level="false")
    for side, lane_id in (("left", 1), ("right", -1)):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(lane_id),
                             type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="2.8", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="white", width=".1")
    ET.SubElement(road, "objects")
    signals = ET.SubElement(road, "signals")
    ET.SubElement(signals, "signal", id=SIGN_ID, s="68", t="-4.2",
                  name=SIGN_NAME, dynamic="no", orientation="-", zOffset="2",
                  country="USA", type="parking_restriction", subtype="restricted_purpose",
                  value="0", unit="none", hOffset="0", pitch="0", roll="0")
    return ET.tostring(root, encoding="unicode")


def check(xml: str | None = None) -> dict:
    root = ET.fromstring(open_drive() if xml is None else xml)
    road = root.find("road")
    if road is None or road.attrib.get("id") != str(ROAD_ID):
        raise ValueError("original narrow-road identity changed")
    lanes = root.findall("road/lanes/laneSection/left/lane") + root.findall(
        "road/lanes/laneSection/right/lane")
    if [(x.attrib.get("id"), x.attrib.get("type"), x.find("width").attrib.get("a"))
            for x in lanes] != [("1", "driving", "2.8"), ("-1", "driving", "2.8")]:
        raise ValueError("two-way narrow-road lane request changed")
    signs = root.findall("road/signals/signal")
    if len(signs) != 1 or any(signs[0].attrib.get(key) != value for key, value in
                              (("id", SIGN_ID), ("name", SIGN_NAME),
                               ("subtype", "restricted_purpose"))):
        raise ValueError("restricted-purpose sign request changed")
    if not (ZONE_X_M[0] < 5 - 2 < 5 + 2 < ZONE_X_M[1]) or not (
            ZONE_Y_M[0] < -2.5 < ZONE_Y_M[1]):
        raise ValueError("subject parking footprint cannot fit requested zone")
    return {"road_id": ROAD_ID, "sign_id": SIGN_ID,
            "requested_restricted_purpose": RESTRICTED_PURPOSE,
            "requested_zone_bounds_m": [ZONE_X_M[0], ZONE_Y_M[0],
                                        ZONE_X_M[1], ZONE_Y_M[1]],
            "official_authority_verified": False, "sign_pixels_verified": False,
            "physical_zone_verified": False}
