"""Build a source-bound two-lane OpenDRIVE crest plan for CPU review.

The generated geometry is checked independently of the diagnostic road.xodr.
CARLA ingestion, actor spawning, and realized sight lines remain unverified.
"""

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_branch_sites import BASE, OUT, check_branch, construct, grade
from site_construction import validate_site

HERE = Path(__file__).resolve().parent
PLAN = HERE / "native-map-plan"
LANE_HALF_WIDTH = 1.75


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def road_source():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", {
        "revMajor": "1", "revMinor": "4", "name": "C129731 planned crest road",
        "version": "1", "north": "10", "south": "-10", "east": "220", "west": "-220",
        "vendor": "scenario-worker-demo CPU plan",
    })
    road = ET.SubElement(root, "road", {"name": "C129731 two-way crest", "length": "440",
                                       "id": "10", "junction": "-1"})
    ET.SubElement(road, "link")
    plan = ET.SubElement(road, "planView")
    ET.SubElement(ET.SubElement(plan, "geometry", {"s": "0", "x": "-220", "y": "0",
                                                   "hdg": "0", "length": "440"}), "line")
    elevations = ET.SubElement(road, "elevationProfile")
    for s, z, slope in ((0, 0, 0), (60, 0, .05), (220, 8, -.05), (380, 0, 0)):
        ET.SubElement(elevations, "elevation", {"s": str(s), "a": str(z),
                                                 "b": str(slope), "c": "0", "d": "0"})
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    for side, lane_id in (("left", "1"), ("center", "0"), ("right", "-1")):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", {"id": lane_id,
                                             "type": "none" if lane_id == "0" else "driving",
                                             "level": "false"})
        ET.SubElement(lane, "link")
        if lane_id != "0":
            ET.SubElement(lane, "width", {"sOffset": "0", "a": "3.5",
                                          "b": "0", "c": "0", "d": "0"})
        ET.SubElement(lane, "roadMark", {"sOffset": "0", "type": "solid", "color": "white",
                                         "width": "0.12", "laneChange": "none"})
    return ET.tostring(root, encoding="unicode") + "\n"


def source_position(x, lane_id):
    if lane_id not in (-1, 1) or x < -220 or x > 220:
        raise ValueError("Position outside planned driving lanes")
    return [x, lane_id * LANE_HALF_WIDTH, grade(x)]


def bind_site(site, road_hash):
    site = copy.deepcopy(site)
    site["map_name"] = "OpenDriveMap"
    site["source_status"] = "diagnostic_fixture"
    site["map_source"] = {"path": "crest-road.xodr", "sha256": road_hash,
                          "status": "cpu_geometry_plan_unverified_in_carla"}
    for name, lane in site["incoming_lanes"].items():
        for row in lane["stations"]:
            row["xyz_m"] = source_position(row["xyz_m"][0], lane["lane_id"])
    route = site["u_turn_route_xyz_m"]
    route[0][1] = -LANE_HALF_WIDTH
    route[1][1] = -LANE_HALF_WIDTH
    route[-1][1] = LANE_HALF_WIDTH
    route[-2][1] = LANE_HALF_WIDTH
    turn_x = site["turn_site_xyz_m"][0]
    site["camera_poses"] = {
        "overview": [turn_x, 0, grade(turn_x) + 30, 0, -45, 0],
        "approach": [turn_x - 20, 0, grade(turn_x - 20) + 7, 0, -10, 0],
        "reference_corner": [turn_x + 10, 10, grade(turn_x + 10) + 8, 180, -15, 0],
        "driver_reference": [1, 0, 1.5, 0, 0, 0],
    }
    # The turn point is a road-centre reference; the actual ego spawn is in
    # lane -1. Native path following and body clearance still require review.
    occluded = site["occluder"]["target_direction"]
    far = site["incoming_lanes"][occluded]["stations"][-1]["xyz_m"]
    turn = site["turn_site_xyz_m"]
    fraction = (150.0 + site["occluder"]["half_extent_xyz_m"][0]) / \
        site["incoming_lanes"][occluded]["stations"][-1]["distance_to_turn_m"]
    site["occluder"]["center_xyz_m"] = [
        turn[0] + fraction * (far[0] - turn[0]),
        turn[1] + fraction * (far[1] - turn[1]),
        turn[2] + 1.5 + fraction * ((far[2] + 1.4) - (turn[2] + 1.5)),
    ]
    validate_site(site)
    return site


def check_source_geometry(xodr, site):
    root = ET.fromstring(xodr)
    road = root.find("road")
    if road is None or road.get("id") != "10" or road.get("length") != "440":
        raise ValueError("Wrong planned road identity or length")
    geometry = road.find("./planView/geometry")
    if geometry is None or geometry.find("line") is None or any(
            geometry.get(k) != v for k, v in (("x", "-220"), ("y", "0"), ("hdg", "0"))):
        raise ValueError("Road plan does not match source station model")
    elevations = road.findall("./elevationProfile/elevation")
    expected = ((0, 0, 0), (60, 0, .05), (220, 8, -.05), (380, 0, 0))
    if [(float(e.get("s")), float(e.get("a")), float(e.get("b"))) for e in elevations] != list(expected):
        raise ValueError("Crest elevation source differs from surveyed plan")
    lanes = {int(lane.get("id")): lane for lane in road.findall("./lanes/laneSection/*/lane")}
    if set(lanes) != {-1, 0, 1} or any(lanes[i].get("type") != "driving" for i in (-1, 1)):
        raise ValueError("Two opposing driving lanes required")
    for name, lane in site["incoming_lanes"].items():
        if lane["road_id"] != 10 or lane["lane_id"] not in (-1, 1):
            raise ValueError("Site lane not in planned road")
        for row in lane["stations"]:
            x = row["xyz_m"][0]
            if row["xyz_m"] != source_position(x, lane["lane_id"]):
                raise ValueError("Site station differs from OpenDRIVE lane/elevation source: " + name)
    if site["map_source"]["sha256"] != hashlib.sha256(xodr.encode()).hexdigest():
        raise ValueError("Site map source hash differs")
    return True


def main():
    PLAN.mkdir(exist_ok=True)
    road = road_source()
    road_path = PLAN / "crest-road.xodr"
    road_path.write_text(road)
    base = json.loads(BASE.read_text())
    rows = []
    for placement in ("near_summit", "approach_to_crest"):
        for direction in ("approach_a", "approach_b"):
            site = bind_site(construct(base, placement, direction), sha(road_path))
            check_branch(site, placement, direction)
            check_source_geometry(road, site)
            name = placement + "__occluded_" + direction
            path = PLAN / (name + ".json")
            path.write_text(json.dumps(site, indent=2, sort_keys=True) + "\n")
            rows.append({"name": name, "path": str(path.relative_to(HERE)), "sha256": sha(path)})
    report = {"status": "cpu_geometry_plan_unverified_in_carla",
              "road": {"path": str(road_path.relative_to(HERE)), "sha256": sha(road_path)},
              "generator_sha256": sha(__file__), "sites": rows,
              "carla_ingestion_verified": False, "physical_acceptance_claimed": False}
    (PLAN / "source-review.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"source_bound_crest_sites": len(rows), "road_sha256": sha(road_path),
                      "carla_ingestion_verified": False}))


if __name__ == "__main__":
    main()
