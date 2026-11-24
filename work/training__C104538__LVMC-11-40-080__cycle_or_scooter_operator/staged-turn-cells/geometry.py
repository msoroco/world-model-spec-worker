"""Staged hill-crest signed right/left turn cells; authored CPU geometry only."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

CELLS = {
    "left": ("C102581", "left_turn", "no_left_turn", 1.0),
    "right": ("C103714", "right_turn", "no_right_turn", -1.0),
}
SIGN_S_M = 56.0
TURN_FIRST_FRAME = 220
TURN_LAST_FRAME = 300
FRAMES = 600
RATE_HZ = 20


def _road(root, road_id, name, start, heading, length, junction, geometry_kind,
          predecessor=None, successor=None, hill=False):
    road = ET.SubElement(root, "road", id=str(road_id), name=name,
                         length=str(length), junction=str(junction))
    link = ET.SubElement(road, "link")
    if predecessor is not None:
        element_type, ident, contact = predecessor
        ET.SubElement(link, "predecessor", elementType=element_type,
                      elementId=str(ident), contactPoint=contact)
    if successor is not None:
        element_type, ident, contact = successor
        ET.SubElement(link, "successor", elementType=element_type,
                      elementId=str(ident), contactPoint=contact)
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0",
                         x=str(start[0]), y=str(start[1]), hdg=str(heading),
                         length=str(length))
    if geometry_kind == "line":
        ET.SubElement(geom, "line")
    else:
        ET.SubElement(geom, "arc", curvature=str(geometry_kind))
    profile = ET.SubElement(road, "elevationProfile")
    if hill:
        # A 1.2 m crest with zero height and slope at both road interfaces.
        ET.SubElement(profile, "elevation", s="0", a="0", b="0",
                      c=str(3.6/1296), d=str(-2.4/46656))
        ET.SubElement(profile, "elevation", s="36", a="1.2", b="0",
                      c=str(-3.6/1296), d=str(2.4/46656))
    else:
        ET.SubElement(profile, "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="1.75", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
    lane_link = ET.SubElement(lane, "link")
    ET.SubElement(lane_link, "predecessor", id="-1")
    ET.SubElement(lane_link, "successor", id="-1")
    ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return road


def open_drive(direction):
    if direction not in CELLS:
        raise ValueError("Unknown signed turn direction")
    cell_id, _, code, curvature_sign = CELLS[direction]
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name=f"{cell_id}-signed-turn-hill-crest", version="1",
                  date="2026-11-24", north="80", south="-80",
                  east="80", west="-80", vendor="full-train-worker")
    incoming = _road(root, 1, "hill_crest_signed_approach", (0, -80), math.pi/2,
                     72, -1, "line", successor=("junction", 100, "start"), hill=True)
    _road(root, 2, "north_through_exit", (0, 8), math.pi/2, 72, -1,
          "line", predecessor=("junction", 100, "end"))
    exit_road = 3 if direction == "right" else 4
    start = (8, 0) if direction == "right" else (-8, 0)
    heading = 0 if direction == "right" else math.pi
    _road(root, exit_road, f"{direction}_turn_exit", start, heading, 72, -1,
          "line", predecessor=("junction", 100, "end"))
    _road(root, 11, "straight_connector", (0, -8), math.pi/2, 16, 100,
          "line", predecessor=("road", 1, "end"),
          successor=("road", 2, "start"))
    _road(root, 12, f"{direction}_arc_connector", (0, -8), math.pi/2,
          4*math.pi, 100, curvature_sign/8,
          predecessor=("road", 1, "end"),
          successor=("road", exit_road, "start"))
    ET.SubElement(incoming.find("signals"), "signal", id=f"1140080{exit_road}",
                  name=code, s=str(SIGN_S_M), t="-3.5", zOffset="2.3",
                  hOffset="0", pitch="0", roll="0", orientation="+",
                  dynamic="no", country="US", type="206", subtype="0",
                  value="0", unit="none")
    junction = ET.SubElement(root, "junction", id="100",
                             name=f"{direction}_and_straight_signed_junction")
    for index, connector in enumerate((11, 12)):
        connection = ET.SubElement(junction, "connection", id=str(index),
                                   incomingRoad="1", connectingRoad=str(connector),
                                   contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def sampled_source(direction, behavior):
    if direction not in CELLS or behavior not in ("obey", "turn"):
        raise ValueError("Unknown controlled branch")
    cell_id, maneuver, sign_code, _ = CELLS[direction]
    sign = 1 if direction == "right" else -1
    rows = []
    for frame in range(FRAMES):
        if frame < TURN_FIRST_FRAME:
            x, y = 0.0, -45 + 37*frame/TURN_FIRST_FRAME
        elif behavior == "obey":
            x, y = 0.0, -8 + .1*(frame-TURN_FIRST_FRAME)
        elif frame <= TURN_LAST_FRAME:
            angle = (frame-TURN_FIRST_FRAME)/80 * math.pi/2
            x = sign*8*(1-math.cos(angle))
            y = -8 + 8*math.sin(angle)
        else:
            x, y = sign*(8+.12*(frame-TURN_LAST_FRAME)), 0.0
        rows.append({"frame":frame, "time_s":frame/RATE_HZ,
                     "body_center_xy_m":[round(x,6),round(y,6)],
                     "road_user_id":"rider-1", "machine_class":"bicycle",
                     "sign_code":sign_code, "sign_id":f"1140080{3 if direction=='right' else 4}",
                     "governed_approach_road_id":1, "governed_approach_lane_id":-1,
                     "mounted":True, "maneuver":maneuver if behavior=="turn" else "through",
                     "source_kind":"authored_cpu_route_plan", "cell_id":cell_id})
    return rows


def check(direction):
    xml = ET.fromstring(open_drive(direction))
    cell_id, maneuver, sign_code, curve = CELLS[direction]
    roads = {r.attrib["id"]:r for r in xml.findall("road")}
    if set(roads) != ({"1","2","3","11","12"} if direction=="right" else
                     {"1","2","4","11","12"}):
        raise ValueError("Signed junction roads differ")
    if len(xml.findall("junction/connection/laneLink")) != 2:
        raise ValueError("Straight and turn connectors required")
    if float(roads["12"].find("planView/geometry/arc").attrib["curvature"]) != curve/8:
        raise ValueError("Turn arc direction differs")
    if roads["1"].find("signals/signal").attrib["name"] != sign_code:
        raise ValueError("Prohibition sign differs")
    elevations = roads["1"].findall("elevationProfile/elevation")
    if len(elevations) != 2 or float(elevations[0].attrib["c"]) <= 0 or \
            float(elevations[1].attrib["c"]) >= 0:
        raise ValueError("Hill-crest profile differs")
    obey, turn = sampled_source(direction,"obey"),sampled_source(direction,"turn")
    if any(a["body_center_xy_m"] != b["body_center_xy_m"]
           for a,b in zip(obey[:TURN_FIRST_FRAME+1],turn[:TURN_FIRST_FRAME+1])):
        raise ValueError("Controlled source positions differ")
    if turn[-1]["body_center_xy_m"][0] * curve >= 0:
        raise ValueError("Turn exit is on the wrong side")
    if obey[-1]["body_center_xy_m"][0] != 0 or turn[-1]["body_center_xy_m"][1] != 0:
        raise ValueError("Straight/turn exit geometry differs")
    return {"passed":True,"cell_id":cell_id,"maneuver":maneuver,
            "sign_code":sign_code,"case_count":2,"frames_per_case":FRAMES,
            "controlled_approach_equal":True,"original_native_observed":False,
            "official_sign_authorization_verified":False}
