"""Authored uncontrolled intersection with bicycle through route and cross motor vehicle."""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

INTERSECTION_NEAR_Y_M = -7.0
LANE_WIDTH_M = 3.5


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C111294-bicycle-motorist-interaction-draft",
                  version="1", date="2026-11-06", north="100", south="-100", east="100",
                  west="-100", vendor="full-train-worker")
    roads = ((1, 0, -100, math.pi/2, 93, -1), (2, 7, 0, 0, 93, -1),
             (3, -100, 0, 0, 93, -1), (4, 0, 7, math.pi/2, 93, -1),
             (13, 0, -7, math.pi/2, 14, 100), (14, -7, 0, 0, 14, 100))
    for ident, x, y, hdg, length, junction in roads:
        road = ET.SubElement(root, "road", id=str(ident), name=f"C111294_{ident}",
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, "link")
        if ident in (1, 3):
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif ident in (2, 4):
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        else:
            incoming,outgoing=(1,4) if ident==13 else (3,2)
            ET.SubElement(link, "predecessor", elementType="road", elementId=str(incoming), contactPoint="end")
            ET.SubElement(link, "successor", elementType="road", elementId=str(outgoing), contactPoint="start")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0",
                             x=str(x), y=str(y), hdg=str(hdg), length=str(length))
        ET.SubElement(geom, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        sec = ET.SubElement(lanes, "laneSection", s="0")
        for side, ids in (("left", (1,)), ("center", (0,)), ("right", (-1,))):
            group = ET.SubElement(sec, side)
            for lane_id in ids:
                lane = ET.SubElement(group, "lane", id=str(lane_id),
                                     type="none" if lane_id == 0 else "driving", level="false")
                if lane_id:
                    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
                    if ident == 13:
                        lane_link = ET.SubElement(lane, "link")
                        ET.SubElement(lane_link, "predecessor", id=str(lane_id))
                        ET.SubElement(lane_link, "successor", id=str(lane_id))
                ET.SubElement(lane, "roadMark", sOffset="0", type="solid" if lane_id == 0 else "broken",
                              color="yellow" if lane_id == 0 else "white", width="0.12")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100", name="two-way-other-vehicle-intersection")
    connection = ET.SubElement(junction, "connection", id="0", incomingRoad="1",
                               connectingRoad="13", contactPoint="start")
    ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    motor_connection = ET.SubElement(junction, "connection", id="1", incomingRoad="3",
                                     connectingRoad="14", contactPoint="start")
    ET.SubElement(motor_connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def route() -> list[list[float]]:
    return [[1.75,round(-40+i*.1,5)] for i in range(801)]


def motor_route() -> list[list[float]]:
    return [[round(-40+i*.1,5),-1.75] for i in range(801)]


def check() -> dict:
    root = ET.fromstring(open_drive())
    if {r.attrib['id'] for r in root.findall('road')} != {'1','2','3','4','13','14'}:
        raise ValueError('Two-way intersection roads missing')
    if len(root.findall('junction/connection/laneLink')) != 2:
        raise ValueError('Through lane link missing')
    if root.findall(".//object") or root.findall('.//signal'):
        raise ValueError('Other-vehicle intersection draft must not author crosswalk or signal control')
    points = route()
    if max(math.dist(a,b) for a,b in zip(points,points[1:])) > .11:
        raise ValueError('Route discontinuity')
    if points[0] != [1.75,-40.0] or points[-1] != [1.75,40.0]:
        raise ValueError('Wrong lane endpoints')
    motor_points=motor_route()
    if max(math.dist(a,b) for a,b in zip(motor_points,motor_points[1:]))>.11 or \
            motor_points[0]!=[-40.,-1.75] or motor_points[-1]!=[40.,-1.75]:
        raise ValueError('Motor-vehicle through route differs')
    return {'passed': True, 'source_scope':'authored OpenDRIVE and sampled proposed route',
            'cell_id':'C111294', 'law_id':'NRS-484B-270-7a', 'route_samples':len(points),
            'motor_route_samples':len(motor_points),
            'intersection_near_y_m':INTERSECTION_NEAR_Y_M,
            'official_device_actors_observed_absent':False, 'native_map_readback_observed':False,
            'original_pixels_observed':False, 'legal_outcome_claimed':False}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=check()
    if args.output:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'road.xodr').write_text(open_drive())
        (args.output/'route.json').write_text(json.dumps(route())+'\n')
        (args.output/'motor-route.json').write_text(json.dumps(motor_route())+'\n')
        (args.output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
