"""Authored depressed highway surface for an excavation request.

The profile is an engineering construction. Original Native waypoint heights,
road pixels and excavation provenance must be reviewed before delivery.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from geometry import ROAD, EXCAVATION, FRAME_COUNT, largest_open_width


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C135702-highway-depressed-surface", version="1",
                  date="2026-11-27", north="100", south="-100",
                  east="100", west="-100", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="narrow-highway-excavation",
                         length="200", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-100", y="0", hdg="0", length="200")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, lane_id in (("left", 1), ("center", 0), ("right", -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", id=str(lane_id),
                             type="none" if lane_id == 0 else "driving", level="false")
        if lane_id:
            ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        if lane_id == 1:
            # The left-lane surface is lowered over x=0..5 only. The
            # right lane and reference line stay at zero elevation.
            for s, z in ((0, 0), (100, -1), (105, 0)):
                ET.SubElement(lane, "height", sOffset=str(s),
                              inner=str(z), outer=str(z))
        ET.SubElement(lane, "roadMark", sOffset="0",
                      type="solid" if lane_id == 0 else "broken",
                      color="yellow" if lane_id == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check() -> dict:
    tree = ET.fromstring(open_drive())
    road = tree.find("road")
    if road is None or len(tree.findall("road")) != 1 or len(tree.findall(".//lane[@type='driving']")) != 2:
        raise ValueError("Two-lane highway excavation geometry absent")
    values = [(float(e.attrib["sOffset"]), float(e.attrib["inner"]),
               float(e.attrib["outer"]))
              for e in tree.findall(".//lane[@id='1']/height")]
    if values != [(0, 0, 0), (100, -1, -1), (105, 0, 0)]:
        raise ValueError("Left-lane depressed highway surface absent")
    return {"passed": True, "road_xy_m": ROAD, "excavation_xy_m": EXCAVATION,
            "left_lane_surface_height_m": values, "original_native_height_confirmed": False,
            "actual_pixels_reviewed": False, "legal_verdict_claimed": False}
