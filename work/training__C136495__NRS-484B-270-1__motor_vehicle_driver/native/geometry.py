"""Authored narrow-road geometry and distinct motor-vehicle/bicycle routes.

Coordinates are engineering requests. Native lane identity and physical motion
must be surveyed after CARLA builds this road.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

ROAD_LENGTH_M = 180.0
LANE_WIDTH_M = 2.75
EGO_START_X_M = 5.0
RIDER_START_X_M = 40.0
EGO_LANE_Y_M = -1.10
RIDER_Y_M = -2.48
EGO_BLUEPRINT = "vehicle.lincoln.mkz_2020"
RIDER_BLUEPRINT = "vehicle.bh.crossbike"


def open_drive() -> str:
    """One straight, bidirectional road with narrow driving lanes."""
    xml = f'''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="c136495_narrow_road" version="1.00" date="2026-11-27" north="0" south="0" east="180" west="0" vendor="worker"/>
  <road name="narrow_road" length="{ROAD_LENGTH_M}" id="136495" junction="-1">
    <link/>
    <type s="0" type="town"><speed max="30" unit="km/h"/></type>
    <planView><geometry s="0" x="0" y="0" hdg="0" length="{ROAD_LENGTH_M}"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneSection s="0">
      <left><lane id="1" type="driving" level="false"><link/><width sOffset="0" a="{LANE_WIDTH_M}" b="0" c="0" d="0"/></lane></left>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="standard" width="0.12"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="{LANE_WIDTH_M}" b="0" c="0" d="0"/></lane></right>
    </laneSection></lanes>
  </road>
</OpenDRIVE>'''
    validate_xml(xml)
    return xml


def validate_xml(xml: str) -> dict:
    root = ET.fromstring(xml)
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib.get("id") != "136495":
        raise ValueError("Wrong narrow-road OpenDRIVE identity")
    widths = {int(lane.attrib["id"]): float(lane.find("width").attrib["a"])
              for lane in root.findall(".//lane") if lane.find("width") is not None}
    if widths != {-1: LANE_WIDTH_M, 1: LANE_WIDTH_M}:
        raise ValueError("Narrow-road lanes differ")
    return {"road_id": 136495, "driving_lane_ids": [-1, 1],
            "lane_width_m": LANE_WIDTH_M, "road_length_m": ROAD_LENGTH_M}


def route(role: str, condition: str) -> list[list[float]]:
    if condition not in {"clear", "intrusion"}:
        raise ValueError("Unknown controlled rider interaction condition")
    if role == "rider":
        start, finish = RIDER_START_X_M, 158.0
        y = lambda x: RIDER_Y_M
    elif role == "ego":
        start, finish = EGO_START_X_M, 158.0
        # Only the intrusion comparison changes the requested motor-vehicle path.
        # Rider path, blueprint, initial pose, cameras and observation window stay fixed.
        def y(x: float) -> float:
            if condition == "clear":
                return EGO_LANE_Y_M
            if x < 70.0 or x > 120.0:
                return EGO_LANE_Y_M
            if x < 82.0:
                return EGO_LANE_Y_M - .48 * (x - 70.0) / 12.0
            if x > 108.0:
                return EGO_LANE_Y_M - .48 * (120.0 - x) / 12.0
            return EGO_LANE_Y_M - .48
    else:
        raise ValueError("Unknown actor role")
    points = [[round(start + i * .2, 4), round(y(start + i * .2), 5)]
              for i in range(int((finish - start) / .2) + 1)]
    if not all(0 <= x <= ROAD_LENGTH_M and -LANE_WIDTH_M < yy < 0
               for x, yy in points):
        raise ValueError("Route leaves authored right driving lane")
    if any(not math.isfinite(v) for point in points for v in point):
        raise ValueError("Route has nonfinite station")
    return points


def plan(condition: str) -> dict:
    ego = route("ego", condition)
    rider = route("rider", condition)
    return {"condition": condition, "road": validate_xml(open_drive()),
            "ego_blueprint": EGO_BLUEPRINT, "rider_blueprint": RIDER_BLUEPRINT,
            "ego_route_points": len(ego), "rider_route_points": len(rider),
            "ego_start_xy_m": ego[0], "rider_start_xy_m": rider[0],
            "rider_identity": "requested human-powered bicycle; original Native blueprint and rider classification require local inspection",
            "driver_intent": "unresolved", "rider_lawful_status": "unresolved",
            "causal_interference": "unresolved", "physical_native_verified": False}
