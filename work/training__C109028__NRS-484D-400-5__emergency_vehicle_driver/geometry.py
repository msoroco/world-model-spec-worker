"""Portable four-way crossroads for the fixed C109028 intersection cell."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

INTERSECTION_X_M = 50.0
EGO_LANE_Y_M = -1.75
OTHER_LANE_X_M = INTERSECTION_X_M + 1.75


def _road(road_id, name, x, y, heading, junction, predecessor, successor):
    link = "<link>"
    if predecessor:
        kind, ident = predecessor
        link += f'<predecessor elementType="{kind}" elementId="{ident}" contactPoint="end"/>'
    if successor:
        kind, ident = successor
        link += f'<successor elementType="{kind}" elementId="{ident}" contactPoint="start"/>'
    link += "</link>"
    lane_links = '<link><predecessor id="-1"/><successor id="-1"/></link>'
    return f'''<road id="{road_id}" name="{name}" length="40" junction="{junction}">{link}
<type s="0" type="rural"><speed max="25" unit="mph"/></type>
<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading}" length="40"><line/></geometry></planView>
<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
<lanes><laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></left>
<center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false">{lane_links}<width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects/><signals/></road>'''


def open_drive():
    east = [(1090, "emergency eastbound approach", -10, 0, 0, -1,
             None, ("junction", 109)),
            (1091, "eastbound crossing", 30, 0, 0, 109,
             ("road", 1090), ("road", 1092)),
            (1092, "eastbound departure", 70, 0, 0, -1,
             ("junction", 109), None)]
    north = [(1093, "counterpart northbound approach", 50, -60,
              math.pi / 2, -1, None, ("junction", 109)),
             (1094, "northbound crossing", 50, -20,
              math.pi / 2, 109, ("road", 1093), ("road", 1095)),
             (1095, "northbound departure", 50, 20,
              math.pi / 2, -1, ("junction", 109), None)]
    roads = "".join(_road(*item) for item in east + north)
    junction = '''<junction id="109" name="emergency approach crossroads">
<connection id="1" incomingRoad="1090" connectingRoad="1091" contactPoint="start"><laneLink from="-1" to="-1"/></connection>
<connection id="2" incomingRoad="1093" connectingRoad="1094" contactPoint="start"><laneLink from="-1" to="-1"/></connection></junction>'''
    return ('<?xml version="1.0" encoding="UTF-8"?><OpenDRIVE>'
            '<header revMajor="1" revMinor="4" name="C109028 emergency crossroads" '
            'version="1" date="2026-11-24" north="60" south="-60" '
            'east="110" west="-10" vendor="worker"/>' + roads + junction +
            '</OpenDRIVE>\n')


def check():
    xml = ET.fromstring(open_drive())
    roads = {int(item.attrib["id"]): item for item in xml.findall("road")}
    if set(roads) != set(range(1090, 1096)):
        raise ValueError("Six road sections required")
    if len(xml.findall("junction/connection")) != 2:
        raise ValueError("Both crossroads approaches require junction links")
    east = roads[1091].find("planView/geometry")
    north = roads[1094].find("planView/geometry")
    if (float(east.attrib["x"]) + 20 != INTERSECTION_X_M or
            float(north.attrib["x"]) != INTERSECTION_X_M or
            float(north.attrib["y"]) + 20 != 0):
        raise ValueError("Crossroads axes differ")
    if not all(road.find("lanes/laneSection/right/lane") is not None
               for road in roads.values()):
        raise ValueError("Driving lanes absent")
    return {"road_sections": 6, "junction_connections": 2,
            "crossing_xy_m": [INTERSECTION_X_M, 0],
            "ego_lane_y_m": EGO_LANE_Y_M,
            "other_lane_x_m": OTHER_LANE_X_M,
            "native_realization_verified": False}
