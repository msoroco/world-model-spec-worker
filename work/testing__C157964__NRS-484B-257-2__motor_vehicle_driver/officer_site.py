"""Validate the authored one-way to two-way officer junction before Native use."""

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


SITE = Path(__file__).with_name("officer-site.xodr")
EGO_ROAD = 157960
JUNCTION = 157961
THROUGH_SOUTH = 157964
THROUGH_NORTH = 157966
YIELD_SIGN = "1579601"


def validate_site(path=SITE):
    path = Path(path)
    root = ET.parse(path).getroot()
    if root.tag != "OpenDRIVE":
        raise ValueError("Officer site is not OpenDRIVE")
    roads = {int(road.get("id")): road for road in root.findall("road")}
    if set(roads) != {157960, 157962, 157963, 157964, 157965, 157966}:
        raise ValueError("Officer junction road inventory differs")
    if root.findall("controller") or root.findall(".//junction/controller"):
        raise ValueError("Officer-control site contains a signal controller")
    junctions = root.findall("junction")
    if len(junctions) != 1 or junctions[0].get("id") != str(JUNCTION):
        raise ValueError("Officer junction identity differs")
    connections = {(int(c.get("incomingRoad")), int(c.get("connectingRoad")))
                   for c in junctions[0].findall("connection")}
    if connections != {(EGO_ROAD, 157962), (THROUGH_SOUTH, 157965),
                       (THROUGH_NORTH, 157965)}:
        raise ValueError("Officer ego or through routes are disconnected")
    ego = roads[EGO_ROAD]
    ego_lanes = ego.findall("./lanes/laneSection/right/lane")
    if (len(ego_lanes) != 1 or ego_lanes[0].get("id") != "-1" or
            ego_lanes[0].get("type") != "driving" or
            ego.findall("./lanes/laneSection/left/lane")):
        raise ValueError("Officer ego approach is not one-way")
    signs = root.findall(".//signals/signal")
    if (len(signs) != 1 or signs[0].get("id") != YIELD_SIGN or
            signs[0].get("type") != "205" or signs[0].get("dynamic") != "no" or
            signs[0].find("validity").get("fromLane") != "-1" or
            signs[0].find("validity").get("toLane") != "-1"):
        raise ValueError("Officer junction lacks the signed ego entrance")
    for road_id in (THROUGH_SOUTH, THROUGH_NORTH):
        road = roads[road_id]
        left = road.findall("./lanes/laneSection/left/lane")
        right = road.findall("./lanes/laneSection/right/lane")
        if (len(left) != 1 or len(right) != 1 or left[0].get("id") != "1" or
                right[0].get("id") != "-1" or
                left[0].get("type") != "driving" or right[0].get("type") != "driving"):
            raise ValueError("Through highway lacks both opposing approaches")
    return {"site_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ego_road_id": EGO_ROAD, "ego_lane_id": -1,
            "through_approaches": [[THROUGH_SOUTH, -1], [THROUGH_NORTH, 1]],
            "junction_id": JUNCTION, "yield_sign_id": YIELD_SIGN,
            "signal_controller_present": False,
            "physical_sign_and_view_status": "unverified"}
