"""Candidate OpenDRIVE bands for roadway, shoulder, sidewalk and trail.

The outer biking lane is an engineering trail stand-in. Its legal access and
municipal sidewalk purpose require independent reviewed sources.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

BANDS = {
    "roadway": (0.0, 3.0),
    "shoulder": (3.0, 4.0),
    "sidewalk": (4.0, 6.0),
    "buffer": (6.0, 7.0),
    "nonmotorized_trail": (7.0, 9.0),
}
LANES = [(-1, "driving", 3.0), (-2, "shoulder", 1.0),
         (-3, "sidewalk", 2.0), (-4, "border", 1.0),
         (-5, "biking", 2.0)]


def map_bytes():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C143766 engineering pedestrian corridor", version="1",
                  north="10", south="-1", east="30", west="0",
                  vendor="worker-candidate")
    road = ET.SubElement(root, "road", name="candidate corridor", length="30", id="1", junction="-1")
    ET.SubElement(road, "link")
    view = ET.SubElement(road, "planView")
    geometry = ET.SubElement(view, "geometry", s="0", x="30", y="0",
                             hdg=str(math.pi), length="30")
    ET.SubElement(geometry, "line")
    elevation = ET.SubElement(road, "elevationProfile")
    ET.SubElement(elevation, "elevation", s="0", a="0", b="0", c="0", d="0")
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    section = ET.SubElement(lanes, "laneSection", s="0")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id, kind, width in LANES:
        lane = ET.SubElement(right, "lane", id=str(lane_id), type=kind, level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(width), b="0", c="0", d="0")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def map_sha256():
    return hashlib.sha256(map_bytes()).hexdigest()


def verify_candidate_map(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != map_sha256():
        raise ValueError("candidate OpenDRIVE source bytes changed")
    root = ET.fromstring(data)
    roads = root.findall("road")
    if len(roads) != 1 or roads[0].get("id") != "1":
        raise ValueError("candidate corridor road identity changed")
    geometry = roads[0].find("./planView/geometry")
    if geometry is None or geometry.find("line") is None:
        raise ValueError("candidate corridor has no line geometry")
    if (float(geometry.get("x")) != 30 or float(geometry.get("y")) != 0 or
            abs(float(geometry.get("hdg"))-math.pi) > 1e-9 or
            float(geometry.get("length")) != 30):
        raise ValueError("candidate corridor coordinate frame changed")
    lanes = roads[0].findall("./lanes/laneSection/right/lane")
    observed = [(int(lane.get("id")), lane.get("type"),
                 float(lane.find("width").get("a"))) for lane in lanes]
    if observed != LANES:
        raise ValueError("candidate corridor lane types or widths changed")
    if sum(width for _, _, width in LANES) != BANDS["nonmotorized_trail"][1]:
        raise ValueError("candidate corridor band offsets changed")
    return {"map_sha256": hashlib.sha256(data).hexdigest(),
            "lane_types": [kind for _, kind, _ in observed],
            "lane_centers_y_m": [1.5, 3.5, 5.0, 6.5, 8.0],
            "limitations": "Engineering OpenDRIVE only; CARLA import and legal sidewalk/trail purpose unverified."}
