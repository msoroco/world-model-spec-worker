"""Proposed straight school-crossing road with source-visible geometry.

OpenDRIVE object declarations are a construction request. Native readback and
camera pixels still have to establish what CARLA actually rendered.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


ROAD_START_X_M = -100.0
ROAD_LENGTH_M = 200.0
LANE_WIDTH_M = 3.5
CROSSWALK_NEAR_X_M = 0.0
CROSSWALK_WIDTH_M = 3.6576
SIGN_X_M = -35.0
MIN_ADVANCE_M = 30.48


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C394563-school-crossing-draft", version="1",
                  date="2026-11-26", north="100", south="-100",
                  east="100", west="-100", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="signed-school-crossing",
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
    for side, lane_id in (("left", 1), ("center", 0), ("right", -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", id=str(lane_id),
                             type="none" if lane_id == 0 else "driving",
                             level="false")
        if lane_id:
            ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                          b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0",
                      type="solid" if lane_id == 0 else "broken",
                      color="yellow" if lane_id == 0 else "white", width="0.12")
    objects = ET.SubElement(road, "objects")
    ET.SubElement(objects, "object", id="39456301", name="yellow-school-crosswalk",
                  type="crosswalk", s=str(-ROAD_START_X_M + CROSSWALK_NEAR_X_M),
                  t="0", zOffset="0", hdg="0", length=str(CROSSWALK_WIDTH_M),
                  width=str(2 * LANE_WIDTH_M), height="0", color="yellow")
    ET.SubElement(objects, "object", id="39456302", name="School-Xing",
                  type="sign", s=str(-ROAD_START_X_M + SIGN_X_M),
                  t=str(-LANE_WIDTH_M - 0.8), zOffset="0.8", hdg="0",
                  length="0.1", width="1.2", height="1.8")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check() -> dict:
    root = ET.fromstring(open_drive())
    roads = root.findall("road")
    if len(roads) != 1 or roads[0].attrib.get("id") != "1":
        raise ValueError("School road missing")
    crossing = root.find(".//object[@name='yellow-school-crosswalk']")
    sign = root.find(".//object[@name='School-Xing']")
    if crossing is None or sign is None:
        raise ValueError("Physical crosswalk or named sign object missing")
    crossing_s = float(crossing.attrib["s"])
    sign_s = float(sign.attrib["s"])
    if not math.isclose(float(crossing.attrib["length"]), CROSSWALK_WIDTH_M,
                        abs_tol=1e-6):
        raise ValueError("Approximately twelve-foot crosswalk differs")
    if crossing.attrib.get("color") != "yellow":
        raise ValueError("Yellow crossing authoring differs")
    if crossing_s - sign_s < MIN_ADVANCE_M:
        raise ValueError("Advance sign is less than 100 ft")
    if sign.attrib["type"] != "sign" or root.findall(".//signal"):
        raise ValueError("School sign construction differs")
    if len(root.findall(".//lane[@type='driving']")) != 2:
        raise ValueError("Two-direction school road differs")
    return {"format": "c394563-school-crossing-geometry-probe-v1",
            "crosswalk_width_m": CROSSWALK_WIDTH_M,
            "sign_advance_m": crossing_s - sign_s,
            "approach_lane_id": -1, "opposing_lane_id": 1,
            "native_map_readback_observed": False,
            "rendered_sign_text_verified": False,
            "city_traffic_engineer_authority_verified": False,
            "physical_completion_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "road.xodr").write_text(open_drive())
        (args.output / "geometry-check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
