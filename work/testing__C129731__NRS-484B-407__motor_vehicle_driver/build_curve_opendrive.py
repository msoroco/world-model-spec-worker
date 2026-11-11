"""Construct a two-lane curve OpenDRIVE plan and source-matched site packets."""

import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from site_construction import validate_site

HERE = Path(__file__).resolve().parent
OUT = HERE / "native-map-plan"
CURVATURE = 1 / 1280
LANE_HALF_WIDTH = 1.75
ROAD_LENGTH = 440


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def center(s):
    if not 0 <= s <= ROAD_LENGTH:
        raise ValueError("Station outside planned road")
    if s <= 220:
        return s - 220, 0.0, 0.0
    arc = s - 220
    theta = CURVATURE * arc
    return math.sin(theta) / CURVATURE, (1 - math.cos(theta)) / CURVATURE, theta


def lane_position(s, lane_id):
    if lane_id not in (-1, 1):
        raise ValueError("Unexpected driving lane")
    x, y, theta = center(s)
    return [x - lane_id * LANE_HALF_WIDTH * math.sin(theta),
            y + lane_id * LANE_HALF_WIDTH * math.cos(theta), 0.0]


def road_source():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", {"revMajor": "1", "revMinor": "4",
                                   "name": "C129731 planned mountain curve", "version": "1",
                                   "north": "30", "south": "-10", "east": "220", "west": "-220",
                                   "vendor": "scenario-worker-demo CPU plan"})
    road = ET.SubElement(root, "road", {"name": "C129731 two-way curve",
                                         "length": str(ROAD_LENGTH), "id": "10", "junction": "-1"})
    ET.SubElement(road, "link")
    view = ET.SubElement(road, "planView")
    ET.SubElement(ET.SubElement(view, "geometry", {"s": "0", "x": "-220",
                                                   "y": "0", "hdg": "0", "length": "220"}), "line")
    ET.SubElement(ET.SubElement(view, "geometry", {"s": "220", "x": "0",
                                                   "y": "0", "hdg": "0", "length": "220"}),
                  "arc", {"curvature": str(CURVATURE)})
    elevations = ET.SubElement(road, "elevationProfile")
    ET.SubElement(elevations, "elevation", {"s": "0", "a": "0", "b": "0",
                                              "c": "0", "d": "0"})
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", {"s": "0", "a": "0", "b": "0",
                                        "c": "0", "d": "0"})
    section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    for side, lane_id in (("left", "1"), ("center", "0"), ("right", "-1")):
        lane_group = ET.SubElement(section, side)
        lane = ET.SubElement(lane_group, "lane", {"id": lane_id,
                                                  "type": "none" if lane_id == "0" else "driving",
                                                  "level": "false"})
        ET.SubElement(lane, "link")
        if lane_id != "0":
            ET.SubElement(lane, "width", {"sOffset": "0", "a": "3.5", "b": "0",
                                          "c": "0", "d": "0"})
        ET.SubElement(lane, "roadMark", {"sOffset": "0", "type": "solid",
                                         "color": "white", "width": "0.12", "laneChange": "none"})
    return ET.tostring(root, encoding="unicode") + "\n"


def source_site(base, road_hash, direction):
    site = copy.deepcopy(base)
    site["source_status"] = "diagnostic_fixture"
    site["map_name"] = "OpenDriveMap"
    site["map_source"] = {"path": "curve-road.xodr", "sha256": road_hash,
                          "status": "cpu_geometry_plan_unverified_in_carla"}
    site["turn_site_xyz_m"] = [0.0, 0.0, 0.0]
    site["centerline_xyz_m"] = [[*center(s)[:2], 0.0] for s in (40, 220, 380, 440)]
    for name, lane_id, sign in (("approach_a", -1, -1), ("approach_b", 1, 1)):
        lane = site["incoming_lanes"][name]
        lane["road_id"] = 10
        lane["lane_id"] = lane_id
        lane["stations"] = [{"distance_to_turn_m": d,
                              "xyz_m": lane_position(220 + sign * d, lane_id)}
                             for d in (5, 80, 180)]
    site["ego_road_lane"] = [10, -1]
    route = site["u_turn_route_xyz_m"]
    route[0] = lane_position(210, -1)
    route[1] = lane_position(220, -1)
    route[2] = [4, 1, 0]
    route[3] = lane_position(215, 1)
    route[4] = lane_position(210, 1)
    site["camera_poses"] = {
        "overview": [0, 0, 30, 0, -45, 0],
        "approach": [-20, 0, 7, 0, -10, 0],
        "reference_corner": [10, 10, 8, 180, -15, 0],
        "driver_reference": [1, 0, 1.5, 0, 0, 0],
    }
    probe_distance = {"short_of_500ft": 150, "at_500ft": 152.4,
                      "beyond_500ft": 160}[site["probe"]]
    far = site["incoming_lanes"][direction]["stations"][-1]["xyz_m"]
    fraction = probe_distance / 180
    site["occluder"] = {
        "blueprint_id": "static.prop.fixture_wall",
        "center_xyz_m": [fraction * far[0], fraction * far[1],
                         1.5 + fraction * (1.4 - 1.5)],
        "half_extent_xyz_m": [2, 2, 2], "yaw_deg": 0,
        "target_direction": direction,
    }
    validate_site(site)
    return site


def check_source_geometry(xodr, site):
    root = ET.fromstring(xodr)
    road = root.find("road")
    if road is None or road.get("id") != "10" or road.get("length") != str(ROAD_LENGTH):
        raise ValueError("Wrong planned road identity")
    geometries = road.findall("./planView/geometry")
    if len(geometries) != 2 or geometries[0].find("line") is None or geometries[1].find("arc") is None:
        raise ValueError("Source lacks line-to-arc geometry")
    if any(geometries[0].get(k) != v for k, v in
           (("s", "0"), ("x", "-220"), ("y", "0"), ("length", "220"))) or any(
           geometries[1].get(k) != v for k, v in
           (("s", "220"), ("x", "0"), ("y", "0"), ("length", "220"))):
        raise ValueError("Source line/arc station changed")
    if float(geometries[1].find("arc").get("curvature")) != CURVATURE:
        raise ValueError("Curve source curvature changed")
    lanes = {int(l.get("id")): l for l in road.findall("./lanes/laneSection/*/lane")}
    if set(lanes) != {-1, 0, 1} or any(lanes[i].get("type") != "driving" for i in (-1, 1)):
        raise ValueError("Two driving lanes missing")
    if site["map_source"]["sha256"] != hashlib.sha256(xodr.encode()).hexdigest():
        raise ValueError("Source hash differs")
    for name, sign in (("approach_a", -1), ("approach_b", 1)):
        lane = site["incoming_lanes"][name]
        if lane["lane_id"] != sign or lane["road_id"] != 10:
            raise ValueError("Wrong source lane")
        for row in lane["stations"]:
            expected = lane_position(220 + sign * row["distance_to_turn_m"], sign)
            if any(abs(a - b) > 1e-8 for a, b in zip(row["xyz_m"], expected)):
                raise ValueError("Curve site station differs from OpenDRIVE source")
    validate_site(site)
    return True


def main():
    OUT.mkdir(exist_ok=True)
    road = road_source()
    path = OUT / "curve-road.xodr"
    path.write_text(road)
    rows = []
    for probe, suffix in (("short_of_500ft", ""), ("at_500ft", "-at"),
                          ("beyond_500ft", "-beyond")):
        base = json.loads((HERE / ("diagnostic-site" + suffix + ".json")).read_text())
        if base["probe"] != probe:
            raise ValueError("Wrong exact source probe")
        for direction in ("approach_a", "approach_b"):
            site = source_site(base, sha(path), direction)
            check_source_geometry(road, site)
            name = "curve_" + probe + "__occluded_" + direction
            site_path = OUT / (name + ".json")
            site_path.write_text(json.dumps(site, indent=2, sort_keys=True) + "\n")
            rows.append({"name": name, "path": str(site_path.relative_to(HERE)),
                         "sha256": sha(site_path)})
    report = {"status": "cpu_geometry_plan_unverified_in_carla",
              "road": {"path": str(path.relative_to(HERE)), "sha256": sha(path)},
              "generator_sha256": sha(__file__), "sites": rows,
              "carla_ingestion_verified": False, "physical_acceptance_claimed": False}
    (OUT / "curve-source-review.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"source_bound_curve_sites": len(rows), "road_sha256": sha(path),
                      "carla_ingestion_verified": False}))


if __name__ == "__main__":
    main()
