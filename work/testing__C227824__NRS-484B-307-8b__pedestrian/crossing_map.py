"""Deterministic engineering OpenDRIVE crossing for C227824.

The lane envelope and walking route are geometry candidates. This module does
not establish legal highway dedication or official traffic-device authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


ROAD_LENGTH_M = 30.0
DRIVING_WIDTH_M = 3.5
SIDEWALK_WIDTH_M = 2.0
ROADWAY_POLYGON_XY_M = [[0.0, -3.5], [30.0, -3.5],
                        [30.0, 3.5], [0.0, 3.5]]
START_XY_M = [15.0, -6.5]
TARGET_XY_M = [15.0, 6.5]


def map_bytes():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", version="1",
                  name="C227824 engineering crossing", vendor="worker-candidate",
                  north="6", south="-6", east="30", west="0")
    road = ET.SubElement(root, "road", id="1", name="candidate crossing road",
                         length="30", junction="-1")
    ET.SubElement(road, "link")
    view = ET.SubElement(road, "planView")
    geometry = ET.SubElement(view, "geometry", s="0", x="0", y="0",
                             hdg="0", length="30")
    ET.SubElement(geometry, "line")
    profile = ET.SubElement(road, "elevationProfile")
    ET.SubElement(profile, "elevation", s="0", a="0", b="0", c="0", d="0")
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    section = ET.SubElement(lanes, "laneSection", s="0")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    for side, sign in (("left", 1), ("right", -1)):
        group = ET.SubElement(section, side)
        for index, kind, width in ((1, "driving", DRIVING_WIDTH_M),
                                   (2, "sidewalk", SIDEWALK_WIDTH_M)):
            lane = ET.SubElement(group, "lane", id=str(sign * index),
                                 type=kind, level="false")
            ET.SubElement(lane, "width", sOffset="0", a=str(width),
                          b="0", c="0", d="0")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def verify(path):
    data = Path(path).read_bytes()
    if data != map_bytes():
        raise ValueError("crossing OpenDRIVE source differs")
    road = ET.fromstring(data).find("road")
    if road is None or road.get("id") != "1":
        raise ValueError("crossing road identity differs")
    observed = {}
    for side in ("left", "right"):
        observed[side] = [(int(lane.get("id")), lane.get("type"),
                           float(lane.find("width").get("a")))
                          for lane in road.findall("./lanes/laneSection/" + side + "/lane")]
    expected = {"left": [(1, "driving", 3.5), (2, "sidewalk", 2.0)],
                "right": [(-1, "driving", 3.5), (-2, "sidewalk", 2.0)]}
    if observed != expected:
        raise ValueError("crossing lane types or dimensions differ")
    if not START_XY_M[1] < -5.5 < -3.5 < TARGET_XY_M[1] or not TARGET_XY_M[1] > 5.5:
        raise ValueError("walking route does not cross both driving lanes")
    return {"map_sha256": hashlib.sha256(data).hexdigest(),
            "roadway_polygon_xy_m": ROADWAY_POLYGON_XY_M,
            "start_xy_m": START_XY_M, "target_xy_m": TARGET_XY_M,
            "legal_highway_extent_verified": False,
            "official_signal_present": False,
            "carla_import_verified": False}


if __name__ == "__main__":
    path = Path(__file__).with_name("candidate-corridor.xodr")
    path.write_bytes(map_bytes())
    print(verify(path))
