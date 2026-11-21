"""Draft OpenDRIVE geometry for a right turn beside a freight loading zone.

The OpenDRIVE objects specify a sign and a curbside bay. CARLA rendering and
legal district classification must be checked from a Native run and site source.
"""

import math
from xml.etree import ElementTree as ET


APPROACH_ROAD = 378304
CONNECTOR_ROAD = 378305
DEPARTURE_ROAD = 378306
JUNCTION = 378307
APPROACH_M = 120.0
LANE_WIDTH_M = 3.6


def _road(root, name, road_id, length, junction, x, y, heading, curvature=None):
    road = ET.SubElement(root, "road", name=name, id=str(road_id),
                         length=str(length), junction=str(junction), rule="RHT")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(x), y=str(y), hdg=str(heading),
                             length=str(length))
    ET.SubElement(geometry, "line" if curvature is None else "arc",
                  **({} if curvature is None else {"curvature": str(curvature)}))
    ET.SubElement(road, "elevationProfile")
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none")
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
    ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="white", width="0.12")
    return road


def build_xodr():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C378304 freight-zone right-turn draft", version="1")
    approach = _road(root, "eastbound approach", APPROACH_ROAD, APPROACH_M,
                     -1, -120, 0, 0)
    ET.SubElement(ET.SubElement(approach, "link"), "successor",
                  elementType="junction", elementId=str(JUNCTION))
    objects = ET.SubElement(approach, "objects")
    ET.SubElement(objects, "object", id="1", name="freight_loading_zone_sign",
                  type="sign", s="82", t="-5.8", zOffset="0", hdg="0",
                  width="0.12", length="0.12", height="2.4", orientation="+")
    ET.SubElement(objects, "object", id="2", name="freight_loading_bay",
                  type="parkingSpace", s="88", t="-5.5", zOffset="0", hdg="0",
                  width="2.5", length="18", height="0", orientation="+")
    curve_length = 5.0 * math.pi / 2.0
    connector = _road(root, "clockwise connector", CONNECTOR_ROAD,
                      curve_length, JUNCTION, 0, 0, 0, -0.2)
    link = ET.SubElement(connector, "link")
    ET.SubElement(link, "predecessor", elementType="road", elementId=str(APPROACH_ROAD),
                  contactPoint="end")
    ET.SubElement(link, "successor", elementType="road", elementId=str(DEPARTURE_ROAD),
                  contactPoint="start")
    departure = _road(root, "southbound exit", DEPARTURE_ROAD, 45,
                      -1, 5, -5, -math.pi / 2)
    ET.SubElement(ET.SubElement(departure, "link"), "predecessor",
                  elementType="junction", elementId=str(JUNCTION))
    junction = ET.SubElement(root, "junction", id=str(JUNCTION), name="right turn")
    connection = ET.SubElement(junction, "connection", id="0",
                               incomingRoad=str(APPROACH_ROAD),
                               connectingRoad=str(CONNECTOR_ROAD), contactPoint="start")
    ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode") + "\n"


def validate_xodr(source):
    root = ET.fromstring(source)
    roads = {int(road.get("id")): road for road in root.findall("road")}
    if set(roads) != {APPROACH_ROAD, CONNECTOR_ROAD, DEPARTURE_ROAD}:
        raise ValueError("Missing exact right-turn roads")
    if float(roads[APPROACH_ROAD].get("length")) < 300 * 0.3048:
        raise ValueError("Approach cannot show the 300-foot branch")
    sign = roads[APPROACH_ROAD].find("./objects/object[@name='freight_loading_zone_sign']")
    bay = roads[APPROACH_ROAD].find("./objects/object[@name='freight_loading_bay']")
    if sign is None or bay is None or not 0 < float(sign.get("s")) < float(bay.get("s")) < APPROACH_M:
        raise ValueError("No ordered freight-zone sign and bay")
    curvature = float(roads[CONNECTOR_ROAD].find("./planView/geometry/arc").get("curvature"))
    if curvature >= 0:
        raise ValueError("Connector is not a right turn")
    return {"approach_road_id": APPROACH_ROAD, "approach_lane_id": -1,
            "outgoing_road_id": DEPARTURE_ROAD, "outgoing_lane_id": -1,
            "approach_length_m": APPROACH_M, "freight_zone_sign_s_m": float(sign.get("s")),
            "freight_zone_bay_s_m": float(bay.get("s")),
            "native_rendering_confirmed": False, "legal_district_confirmed": False}
