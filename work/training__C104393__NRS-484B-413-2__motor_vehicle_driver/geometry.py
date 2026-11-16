"""Authored C104393 hill-crest turn geometry and signal-start stations.

CPU geometry only: no CARLA map readback, captured signal or video is claimed.
"""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

APPROACH_M = 130.0
CREST_STATION_M = 65.0
CREST_HEIGHT_M = 2.0
TURN_RADIUS_M = 20.0
LANE_WIDTH_M = 3.5
EGO_Y_M = -LANE_WIDTH_M / 2
OTHER_Y_M = LANE_WIDTH_M / 2
FEET = (90, 100, 110, 290, 300, 310)
SAMPLE_M = 0.1


def elevation(station_m):
    if not 0 <= station_m <= APPROACH_M:
        raise ValueError("Elevation station outside authored approach")
    half = CREST_STATION_M
    if station_m <= half:
        u = station_m / half
        return CREST_HEIGHT_M * (3 * u * u - 2 * u * u * u)
    u = (station_m - half) / half
    return CREST_HEIGHT_M * (1 - 3 * u * u + 2 * u * u * u)


def signal_start(feet):
    if feet not in FEET:
        raise ValueError("Unplanned signal interval")
    return round(APPROACH_M - feet * 0.3048, 6)


def route(turn_radius_m=TURN_RADIUS_M):
    if turn_radius_m not in (20.0, 24.0):
        raise ValueError("Unplanned turn radius")
    points = []
    for index in range(round(APPROACH_M / SAMPLE_M) + 1):
        s = round(index * SAMPLE_M, 6)
        points.append([round(s - APPROACH_M, 6), EGO_Y_M,
                       round(elevation(s), 8)])
    # A left curve starts at the end of the direct hill-crest course. This is
    # an authored centerline proposal, pending Native lane and body readback.
    lane_radius = turn_radius_m + LANE_WIDTH_M / 2
    for index in range(1, math.ceil(math.pi * lane_radius / (2 * SAMPLE_M)) + 1):
        angle = min(index * SAMPLE_M / lane_radius, math.pi / 2)
        points.append([round(lane_radius * math.sin(angle), 6),
                       round(turn_radius_m - lane_radius * math.cos(angle), 6), 0.0])
    return points


def open_drive(turn_radius_m=TURN_RADIUS_M):
    if turn_radius_m not in (20.0, 24.0):
        raise ValueError("Unplanned turn radius")
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C104393-hill-crest-turn",
                  version="1", date="2026-11-07", north="60", south="-20",
                  east="40", west="-140", vendor="full-train-worker")
    roads = ((1, -APPROACH_M, 0.0, 0.0, APPROACH_M, "line"),
             (2, 0.0, 0.0, 0.0, math.pi * turn_radius_m / 2, "arc"))
    for road_id, x, y, heading, length, kind in roads:
        road = ET.SubElement(root, "road", id=str(road_id), name=f"C104393_{road_id}",
                             length=str(length), junction="-1")
        link = ET.SubElement(road, "link")
        if road_id == 1:
            ET.SubElement(link, "successor", elementType="road", elementId="2", contactPoint="start")
        else:
            ET.SubElement(link, "predecessor", elementType="road", elementId="1", contactPoint="end")
        geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                                 s="0", x=str(x), y=str(y), hdg=str(heading), length=str(length))
        ET.SubElement(geometry, kind, **({"curvature": str(1 / turn_radius_m)} if kind == "arc" else {}))
        profile = ET.SubElement(road, "elevationProfile")
        half = CREST_STATION_M
        if road_id == 1:
            ET.SubElement(profile, "elevation", s="0", a="0", b="0",
                          c=str(3 * CREST_HEIGHT_M / half**2),
                          d=str(-2 * CREST_HEIGHT_M / half**3))
            ET.SubElement(profile, "elevation", s=str(half), a=str(CREST_HEIGHT_M),
                          b="0", c=str(-3 * CREST_HEIGHT_M / half**2),
                          d=str(2 * CREST_HEIGHT_M / half**3))
        else:
            ET.SubElement(profile, "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, lane_id in (("left", 1), ("right", -1)):
            group = ET.SubElement(section, side)
            lane = ET.SubElement(group, "lane", id=str(lane_id), type="driving", level="false")
            lane_link = ET.SubElement(lane, "link")
            ET.SubElement(lane_link, "predecessor", id=str(lane_id))
            ET.SubElement(lane_link, "successor", id=str(lane_id))
            ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
            ET.SubElement(lane, "roadMark", sOffset="0", type="broken", color="white", width="0.12")
        center = ET.SubElement(section, "center")
        lane_zero = ET.SubElement(center, "lane", id="0", type="none", level="false")
        ET.SubElement(lane_zero, "roadMark", sOffset="0", type="solid",
                      color="yellow", width="0.12")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def check():
    document = ET.fromstring(open_drive())
    roads = document.findall("road")
    assert len(roads) == 2
    assert roads[0].find("link/successor").get("elementId") == "2"
    assert roads[1].find("link/predecessor").get("elementId") == "1"
    assert len(roads[0].findall("elevationProfile/elevation")) == 2
    assert abs(elevation(0)) < 1e-8 and abs(elevation(APPROACH_M)) < 1e-8
    assert abs(elevation(CREST_STATION_M) - CREST_HEIGHT_M) < 1e-8
    points = route()
    alternate = route(24.0)
    assert len(alternate) > len(points)
    assert len(ET.fromstring(open_drive(24.0)).findall("road")) == 2
    gaps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    assert max(gaps) < 0.101
    assert all(point[1] == EGO_Y_M for point in points[:1301])
    assert OTHER_Y_M - EGO_Y_M == LANE_WIDTH_M
    starts = {str(feet): signal_start(feet) for feet in FEET}
    assert all(0 < station < APPROACH_M for station in starts.values())
    assert starts["110"] > CREST_STATION_M > starts["290"]
    assert starts["90"] > starts["100"] > starts["110"]
    assert starts["290"] > starts["300"] > starts["310"]
    for feet, station in starts.items():
        assert abs((APPROACH_M - station) - int(feet) * 0.3048) < 1e-5
    return {"format": "c104393-authored-hill-crest-geometry-v1", "passed": True,
            "native_executed": False, "signal_observed": False,
            "frozen_cell": {"layout": "hill_crest", "maneuver": "turn", "control": "other_vehicle"},
            "approach_m": APPROACH_M, "crest_station_m": CREST_STATION_M,
            "crest_height_m": CREST_HEIGHT_M, "turn_radius_m": TURN_RADIUS_M,
            "other_vehicle": {"lane_center_y_m": OTHER_Y_M, "opposing_heading_deg": 180,
                              "placement_requires_native_survey": True},
            "signal_start_stations_m": starts, "route_points": len(points),
            "maximum_route_step_m": round(max(gaps), 6),
            "limitations": ["Authored OpenDRIVE has not been loaded in Native",
                            "No original signal, actor, pose, weather or pixels have been observed"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "scene.xodr").write_text(open_drive())
        (args.output / "route.json").write_text(json.dumps(route()) + "\n")
        (args.output / "geometry-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
