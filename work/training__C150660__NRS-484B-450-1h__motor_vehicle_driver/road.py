"""Authored one-way road with a protected roadside refuge specification.

The XML and spawned geometry are construction requests. An original map survey
and independent review must establish an actual safety zone and adjacent curb.
"""

import xml.etree.ElementTree as ET

LENGTH_M = 200.0
ZONE_START_M = 80.0
ZONE_END_M = 100.0
CURB_Y_M = -7.4
ZONE_NEAR_Y_M = -4.5
EGO_LANE_ID = -1


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C150660-zone",
                  version="1", date="2026-11-27", north="20", south="-20",
                  east="200", west="0", vendor="worker")
    road = ET.SubElement(root, "road", id="1", name="one_way_zone_road",
                         length=str(LENGTH_M), junction="-1", rule="RHT")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="0", y="0", hdg="0", length=str(LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    driving = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
    ET.SubElement(driving, "width", sOffset="0", a="3.7", b="0", c="0", d="0")
    ET.SubElement(driving, "roadMark", sOffset="0", type="broken", color="white", width=".12")
    shoulder = ET.SubElement(right, "lane", id="-2", type="shoulder", level="false")
    ET.SubElement(shoulder, "width", sOffset="0", a="3.7", b="0", c="0", d="0")
    ET.SubElement(shoulder, "roadMark", sOffset="0", type="solid", color="white", width=".12")
    objects = ET.SubElement(road, "objects")
    for index, station in enumerate(range(80, 101, 2)):
        ET.SubElement(objects, "object", id=str(700 + index),
                      name="refuge_edge_marker", type="barrier", s=str(station),
                      t=str(ZONE_NEAR_Y_M), zOffset="0", validLength="0",
                      orientation="+", length="1.5", width=".15", height=".6")
    for index, station in enumerate((ZONE_START_M, ZONE_END_M)):
        ET.SubElement(objects, "object", id=str(750 + index),
                      name="refuge_end_marker", type="pole", s=str(station),
                      t="-4.6", zOffset="0", validLength="0", orientation="+",
                      length=".15", width=".15", height="1.0")
    return ET.tostring(root, encoding="unicode")


def check():
    root = ET.fromstring(open_drive())
    road = root.find("road[@id='1']")
    if road is None or float(road.get("length")) != LENGTH_M:
        raise ValueError("One-way road specification changed")
    driving = road.find("lanes/laneSection/right/lane[@id='-1']")
    shoulder = road.find("lanes/laneSection/right/lane[@id='-2']")
    markers = road.findall("objects/object")
    if driving is None or shoulder is None or len(markers) != 13:
        raise ValueError("Safety-zone roadside construction incomplete")
    if driving.get("type") != "driving" or shoulder.get("type") != "shoulder":
        raise ValueError("Lane/shoulder types differ")
    return {"passed": True, "road_id": 1, "one_way_requested": True,
            "zone_station_m": [ZONE_START_M, ZONE_END_M],
            "zone_edge_marker_count": 11, "end_marker_count": 2,
            "adjacent_curb_y_m": CURB_Y_M,
            "native_map_readback_pending": True,
            "official_safety_zone_status_pending_review": True}
