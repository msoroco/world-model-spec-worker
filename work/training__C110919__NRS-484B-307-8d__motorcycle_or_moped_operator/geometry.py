"""Authored C110919 motorcycle signal-failure right-turn geometry."""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

STOP_LINE_Y_M = -14.0
CROSSWALK_NEAR_Y_M = -11.0
INTERSECTION_NEAR_Y_M = -7.0
LANE_WIDTH_M = 3.5


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C110919-red-right-turn-draft",
                  version="1", date="2026-11-06", north="100", south="-100", east="100",
                  west="-100", vendor="full-train-worker")
    roads = ((1, 0, -100, math.pi/2, 93, -1), (2, 7, 0, 0, 93, -1),
             (3, -100, 0, 0, 93, -1), (4, 0, 7, math.pi/2, 93, -1),
             (13, 0, -7, math.pi/2, 7*math.pi/2, 100))
    for ident, x, y, hdg, length, junction in roads:
        road = ET.SubElement(root, "road", id=str(ident), name=f"C110919_{ident}",
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, "link")
        if ident in (1, 3):
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif ident in (2, 4):
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        else:
            ET.SubElement(link, "predecessor", elementType="road", elementId="1", contactPoint="end")
            ET.SubElement(link, "successor", elementType="road", elementId="2", contactPoint="start")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0",
                             x=str(x), y=str(y), hdg=str(hdg), length=str(length))
        if ident == 13:
            ET.SubElement(geom, "arc", curvature=str(-1/7))
        else:
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
        objects = ET.SubElement(road, "objects")
        if ident == 1:
            ET.SubElement(objects, "object", id="501", name="nearest-side-crosswalk",
                          type="crosswalk", s="89", t="0", zOffset="0", hdg="0",
                          length="2", width="7", height="0")
            ET.SubElement(objects, "object", id="502", name="stop-line", type="roadMark",
                          s="86", t="0", zOffset="0", hdg="0", length="0.2", width="7", height="0")
            ET.SubElement(objects, "object", id="504", name="motorcycle-detector-loop-proposal",
                          type="sensor", s="82", t="-1.75", zOffset="0", hdg="0",
                          length="2", width="1.5", height="0")
        if ident == 2:
            ET.SubElement(objects, "object", id="503", name="destination-pedestrian-crosswalk",
                          type="crosswalk", s="3", t="0", zOffset="0", hdg="0",
                          length="2", width="7", height="0")
        signals = ET.SubElement(road, "signals")
        if ident == 1:
            ET.SubElement(signals, "signal", id="601", name="south-approach-circular-red",
                          s="87", t="-3.5", zOffset="4", hOffset="0", pitch="0", roll="0",
                          orientation="+", dynamic="yes", country="US", type="1000001",
                          subtype="0", value="0", unit="")
        if ident == 3:
            ET.SubElement(signals, "signal", id="602", name="cross-traffic-cycle-head",
                          s="87", t="-3.5", zOffset="4", hOffset="0", pitch="0", roll="0",
                          orientation="+", dynamic="yes", country="US", type="1000001",
                          subtype="0", value="0", unit="")
    junction = ET.SubElement(root, "junction", id="100", name="two-way-right-turn")
    connection = ET.SubElement(junction, "connection", id="0", incomingRoad="1",
                               connectingRoad="13", contactPoint="start")
    ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def route() -> list[list[float]]:
    # Rightmost approach lane, a 5.25 m centerline radius, then rightmost eastbound lane.
    points = [[1.75, round(-40+i*.1, 5)] for i in range(331)]
    for i in range(1, 159):
        theta = math.pi-i*(math.pi/2)/158
        points.append([round(7+5.25*math.cos(theta), 5), round(-7+5.25*math.sin(theta), 5)])
    points += [[round(7+i*.1, 5), -1.75] for i in range(1, 331)]
    return points


def check() -> dict:
    root = ET.fromstring(open_drive())
    if {r.attrib['id'] for r in root.findall('road')} != {'1','2','3','4','13'}:
        raise ValueError('Two-way intersection roads missing')
    if len(root.findall('junction/connection/laneLink')) != 1:
        raise ValueError('Right-turn lane link missing')
    if len(root.findall(".//object[@type='crosswalk']")) != 2 or len(root.findall(".//object[@name='stop-line']")) != 1:
        raise ValueError('Stop condition_a hierarchy missing')
    if len(root.findall(".//signal[@id='601']")) != 1:
        raise ValueError('Governing signal proposal missing')
    if len(root.findall(".//signal[@id='602']")) != 1 or \
       len(root.findall(".//object[@name='motorcycle-detector-loop-proposal']")) != 1:
        raise ValueError('Cross-cycle or detector proposal missing')
    points = route()
    if max(math.dist(a,b) for a,b in zip(points,points[1:])) > .11:
        raise ValueError('Route discontinuity')
    if points[0] != [1.75,-40.0] or points[-1] != [40.0,-1.75]:
        raise ValueError('Wrong lane endpoints')
    return {'passed': True, 'source_scope':'authored OpenDRIVE and sampled proposed route',
            'cell_id':'C110919', 'law_id':'NRS-484B-307-8d', 'route_samples':len(points),
            'stop_line_y_m':STOP_LINE_Y_M, 'crosswalk_near_y_m':CROSSWALK_NEAR_Y_M,
            'intersection_near_y_m':INTERSECTION_NEAR_Y_M,
            'physical_signal_state_observed':False, 'native_map_readback_observed':False,
            'detector_fault_injection_observed':False,
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
        (args.output/'geometry-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
