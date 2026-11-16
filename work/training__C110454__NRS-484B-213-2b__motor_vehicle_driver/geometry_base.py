"""Authored C110454 two-way intersection and controlled left-of-center routes.

All coordinates and body footprints are CPU construction proposals. A Native
map readback and original vehicle poses are required before delivery selection.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

LANE_WIDTH_M = 3.5
HALF_ROAD_M = 3.5
INTERSECTION_HALF_M = 7.0
STATUTORY_APPROACH_M = 100 * 0.3048
STEP_M = 0.1
BODY_HALF_LENGTH_M = 2.6
BODY_HALF_WIDTH_M = 1.1
EXCURSION_WINDOWS = {"reference": (-60.0, -40.0),
                     "contrast": (-28.0, -8.0)}
PARK_BAY = (8.0, 35.0, -7.0, -3.5)


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C110454-two-way-park-intersection-draft", version="1",
                  date="2026-11-06", north="100", south="-100", east="100",
                  west="-100", vendor="full-train-worker")
    roads = ((1, -100, 0, 0, 93, -1), (2, 7, 0, 0, 93, -1),
             (3, 0, -100, math.pi / 2, 93, -1),
             (4, 0, 7, math.pi / 2, 93, -1),
             (13, -7, 0, 0, 14, 100),
             (14, 0, -7, math.pi / 2, 14, 100))
    for ident, x, y, heading, length, junction_id in roads:
        road = ET.SubElement(root, "road", id=str(ident),
                             name=f"C110454_{ident}", length=str(length),
                             junction=str(junction_id))
        link = ET.SubElement(road, "link")
        if ident in (1, 3):
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif ident in (2, 4):
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        else:
            incoming, outgoing = (1, 2) if ident == 13 else (3, 4)
            ET.SubElement(link, "predecessor", elementType="road",
                          elementId=str(incoming), contactPoint="end")
            ET.SubElement(link, "successor", elementType="road",
                          elementId=str(outgoing), contactPoint="start")
        geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                                 s="0", x=str(x), y=str(y), hdg=str(heading),
                                 length=str(length))
        ET.SubElement(geometry, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                      s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, lane_ids in (("left", (1,)), ("center", (0,)),
                               ("right", (-1,))):
            group = ET.SubElement(section, side)
            for lane_id in lane_ids:
                lane = ET.SubElement(group, "lane", id=str(lane_id),
                                     type="none" if lane_id == 0 else "driving",
                                     level="false")
                if lane_id:
                    if ident in (13, 14):
                        lane_link = ET.SubElement(lane, "link")
                        ET.SubElement(lane_link, "predecessor", id=str(lane_id))
                        ET.SubElement(lane_link, "successor", id=str(lane_id))
                    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                                  b="0", c="0", d="0")
                ET.SubElement(lane, "roadMark", sOffset="0",
                              type="solid" if lane_id == 0 else "broken",
                              color="yellow" if lane_id == 0 else "white",
                              width="0.12")
        objects = ET.SubElement(road, "objects")
        if ident == 2:
            # An authored parking surface proposal; Native mesh/pixels are unverified.
            ET.SubElement(objects, "object", id="501", name="right-side-parking-bay",
                          type="parkingSpace", s="1", t="-5.25", zOffset="0",
                          hdg="0", length="27", width="3.5", height="0")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100", name="two_way_crossing")
    for index, (incoming, connector) in enumerate(((1, 13), (3, 14))):
        connection = ET.SubElement(junction, "connection", id=str(index),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connector), contactPoint="start")
        for lane_id in (-1, 1):
            ET.SubElement(connection, "laneLink", **{"from": str(lane_id),
                                                       "to": str(lane_id)})
    return ET.tostring(root, encoding="unicode")


def _smoothstep(value: float) -> float:
    return value * value * (3 - 2 * value)


def route(case: str) -> list[list[float]]:
    if case not in EXCURSION_WINDOWS:
        raise ValueError("Unknown controlled case")
    onset, end = EXCURSION_WINDOWS[case]
    points = []
    for index in range(round((12.0 - (-70.0)) / STEP_M) + 1):
        x = round(-70.0 + index * STEP_M, 4)
        if x < onset or x > end:
            y = -1.75
        elif x <= onset + 5:
            y = -1.75 + 3.5 * _smoothstep((x - onset) / 5)
        elif x <= end - 5:
            y = 1.75
        else:
            y = 1.75 - 3.5 * _smoothstep((x - end + 5) / 5)
        points.append([x, round(y, 6)])
    # Same right-side parking maneuver after the intersection for both probes.
    for index in range(1, 81):
        t = index / 80
        points.append([round(12 + 8*t, 4),
                       round(-1.75 - 3.5*_smoothstep(t), 6)])
    return points


def _body(x: float, y: float) -> tuple[tuple[float, float], ...]:
    return tuple((x + dx, y + dy) for dx, dy in
                 ((-BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M),
                  (-BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
                  (BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
                  (BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M)))


def check() -> dict:
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    root = ET.fromstring(open_drive())
    roads = {int(r.attrib["id"]): r for r in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise ValueError("Two-way crossing roads missing")
    if len(root.findall("junction/connection")) != 2:
        raise ValueError("Intersection links missing")
    if len(root.findall(".//object[@type='parkingSpace']")) != 1:
        raise ValueError("Parking surface missing")
    pavement = unary_union((box(-100, -HALF_ROAD_M, 100, HALF_ROAD_M),
                            box(-HALF_ROAD_M, -100, HALF_ROAD_M, 100),
                            box(PARK_BAY[0], PARK_BAY[2], PARK_BAY[1], PARK_BAY[3])))
    outcomes = {}
    for case in EXCURSION_WINDOWS:
        points = route(case)
        if max(math.dist(a, b) for a, b in zip(points, points[1:])) > 0.15:
            raise ValueError("Route sample discontinuity")
        for x, y in points:
            if not pavement.covers(Polygon(_body(x, y))):
                raise ValueError("Prospective full body leaves authored pavement")
        # Original vehicle body and Native road containment remain unverified.
        left = [(x, y) for x, y in points if all(vertex[1] > 0
                for vertex in _body(x, y))]
        if not left:
            raise ValueError("No proposed full-body left-of-center interval")
        first_left = left[0][0]
        last_left = left[-1][0]
        # Front body station is used because the ban starts on approach.
        nearest_front_to_intersection = -INTERSECTION_HALF_M - (last_left + BODY_HALF_LENGTH_M)
        intersects_zone = any(x + BODY_HALF_LENGTH_M >= -INTERSECTION_HALF_M - STATUTORY_APPROACH_M
                              for x, y in left)
        outcomes[case] = {
            "first_full_body_left_x_m": first_left,
            "last_full_body_left_x_m": last_left,
            "nearest_front_distance_to_intersection_m": round(nearest_front_to_intersection, 4),
            "sampled_left_body_intersects_100_ft_approach": intersects_zone,
            "route_points": len(points),
            "parking_end_xy_m": points[-1],
        }
    if outcomes["reference"]["sampled_left_body_intersects_100_ft_approach"]:
        raise ValueError("Reference full body enters prohibited approach zone")
    if not outcomes["contrast"]["sampled_left_body_intersects_100_ft_approach"]:
        raise ValueError("Contrast lacks zone overlap")
    if outcomes["reference"]["parking_end_xy_m"] != outcomes["contrast"]["parking_end_xy_m"]:
        raise ValueError("Controlled parking endpoint changed")
    return {"passed": True, "scope": "authored OpenDRIVE and sampled prospective body only",
            "law_id": "NRS-484B-213-2b", "cell_id": "C110454",
            "one_way_highway_assumed": False,
            "intersection_native_verified": False,
            "parking_pixels_verified": False,
            "statutory_approach_m": STATUTORY_APPROACH_M,
            "comparison_variable": "left_side_entry_distance_to_intersection",
            "case_results": outcomes,
            "native_or_legal_outcome_claimed": False}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = check()
    if args.output:
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=False)
        (output / "road.xodr").write_text(open_drive())
        for case in EXCURSION_WINDOWS:
            (output / ("route-" + case + ".json")).write_text(json.dumps(route(case)))
        (output / "check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
