"""CPU geometry proposal for the two controlled NRS 484B.400(2)(a) cases.

This is an authored OpenDRIVE/route model. It does not establish that CARLA
loads the map, that the vehicle tracks the path, or that the rendered views
show the required physical distinction.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

LANE_WIDTH_M = 3.5
ROAD_HALF_WIDTH_M = 7.0
SAMPLE_STEP_M = 0.1
CASE_PLACEMENTS = {"controlled_1": -1.75, "controlled_2": -5.25}


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C329610-two-way-left-turn-draft", version="1", date="2026-11-05", north="100", south="-100", east="100", west="-100", vendor="full-train-worker")
    # Four orthogonal two-way legs, with two 3.5 m driving lanes per direction.
    # The junction's lane links remain an authored proposal pending Native query.
    roads = [(1, -100, 0, 0, 93, -1), (2, 7, 0, 0, 93, -1),
             (3, 0, -100, math.pi / 2, 93, -1), (4, 0, 7, math.pi / 2, 93, -1),
             (13, -7, 0, 0, 7 * math.pi / 2, 100)]
    for ident, x, y, heading, length, junction in roads:
        road = ET.SubElement(root, "road", id=str(ident), name=f"C329610_{ident}", length=str(length), junction=str(junction))
        link = ET.SubElement(road, "link")
        if ident == 1:
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif ident == 4:
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        elif ident == 13:
            ET.SubElement(link, "predecessor", elementType="road", elementId="1", contactPoint="end")
            ET.SubElement(link, "successor", elementType="road", elementId="4", contactPoint="start")
        geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x=str(x), y=str(y), hdg=str(heading), length=str(length))
        if ident == 13:
            ET.SubElement(geometry, "arc", curvature=str(1 / 7))
        else:
            ET.SubElement(geometry, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, ids in (("left", (1, 2)), ("center", (0,)), ("right", (-1, -2))):
            group = ET.SubElement(section, side)
            for lane_id in ids:
                lane = ET.SubElement(group, "lane", id=str(lane_id), type="none" if lane_id == 0 else "driving", level="false")
                if lane_id:
                    if ident == 13:
                        lane_link = ET.SubElement(lane, "link")
                        ET.SubElement(lane_link, "predecessor", id=str(lane_id))
                        ET.SubElement(lane_link, "successor", id=str(lane_id))
                    # Both turn lanes must leave a nonzero inner radius on the
                    # seven-meter connector arc for the pinned lane parser.
                    connector_width = 3.3 if ident == 13 else LANE_WIDTH_M
                    ET.SubElement(lane, "width", sOffset="0", a=str(connector_width), b="0", c="0", d="0")
                ET.SubElement(lane, "roadMark", sOffset="0", type="solid" if lane_id == 0 else "broken", color="yellow" if lane_id == 0 else "white", width="0.12")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100", name="two_way_left_turn")
    for index, lane in enumerate((-1, -2)):
        connection = ET.SubElement(junction, "connection", id=str(index), incomingRoad="1", connectingRoad="13", contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": str(lane), "to": str(lane)})
    return ET.tostring(root, encoding="unicode")


def route(placement_y_m: float, start_x_m: float = -50.0, turn_entry_x_m: float = -7.0) -> list[list[float]]:
    if placement_y_m not in CASE_PLACEMENTS.values():
        raise ValueError("Unknown controlled approach placement")
    approach_count = round((turn_entry_x_m - start_x_m) / SAMPLE_STEP_M)
    points = [[round(start_x_m + i * SAMPLE_STEP_M, 4), placement_y_m] for i in range(approach_count + 1)]
    # Cubic Bezier joins the measured approach lane to the northbound inside
    # lane. Far-lane crossing is intentional and must be visible in Native video.
    p0 = (turn_entry_x_m, placement_y_m)
    p1 = (-3.0, placement_y_m)
    p2 = (1.75, 0.0)
    p3 = (1.75, 7.0)
    for i in range(1, 151):
        t = i / 150
        x = (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t*t*p2[0] + t**3*p3[0]
        y = (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t*t*p2[1] + t**3*p3[1]
        points.append([x, y])
    points.extend([[1.75, round(7 + i * SAMPLE_STEP_M, 4)] for i in range(1, 431)])
    return points


def check() -> dict:
    root = ET.fromstring(open_drive())
    assert len(root.findall("road")) == 5
    assert len(root.findall("junction/connection")) == 2
    assert not root.findall(".//signal")
    roads = {int(road.attrib["id"]): road for road in root.findall("road")}
    assert roads[1].find("link/successor").attrib["elementId"] == "100"
    assert roads[13].find("link/predecessor").attrib["elementId"] == "1"
    assert roads[13].find("link/successor").attrib["elementId"] == "4"
    assert roads[4].find("link/predecessor").attrib["elementId"] == "100"
    assert {int(c.find("laneLink").attrib["from"]) for c in root.findall("junction/connection")} == {-1, -2}
    from shapely.geometry import LineString, Point, Polygon, box
    from shapely.ops import unary_union
    surface = unary_union((box(-100, -ROAD_HALF_WIDTH_M, 100, ROAD_HALF_WIDTH_M),
                           box(-ROAD_HALF_WIDTH_M, -100, ROAD_HALF_WIDTH_M, 100)))
    results = {}
    for suffix, lateral in CASE_PLACEMENTS.items():
        points = route(lateral)
        assert all(surface.covers(Point(x, y)) for x, y in points)
        gaps = [math.dist(a, b) for a, b in zip(points, points[1:])]
        assert max(gaps) < 0.3, "Route has a discontinuity"
        assert all(y == lateral for x, y in points if x <= -7), "Approach placement changed"
        assert all(-ROAD_HALF_WIDTH_M < y < 0 for x, y in points if x <= -7)
        # The rectangle is only an asset-size proxy. Native bounding boxes and
        # junction lane surfaces still require a live pre-motion survey.
        for a, b in zip(points, points[1:]):
            angle = math.atan2(b[1]-a[1], b[0]-a[0])
            c, s = math.cos(angle), math.sin(angle)
            body = Polygon([(a[0]+c*u-s*v, a[1]+s*u+c*v) for u,v in
                            ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))])
            assert surface.covers(body), "Prospective body leaves authored pavement"
        results[suffix] = {"approach_lateral_m": lateral, "route_points": len(points),
                           "route_length_m": round(LineString(points).length, 3),
                           "maximum_sample_gap_m": round(max(gaps), 4)}
    assert results["controlled_1"]["approach_lateral_m"] != results["controlled_2"]["approach_lateral_m"]
    return {"passed": True, "scope": "authored geometry and prospective body proxy only",
            "native_verified": False, "junction_lane_links_native_verified": False,
            "right_half_y_m": [-7, 0], "centerline_y_m": 0,
            "cases": results}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = check()
    if args.output:
        destination = Path(args.output)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "scene.xodr").write_text(open_drive())
        for suffix, lateral in CASE_PLACEMENTS.items():
            (destination / f"route-{suffix}.json").write_text(json.dumps(route(lateral)))
        (destination / "geometry-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
