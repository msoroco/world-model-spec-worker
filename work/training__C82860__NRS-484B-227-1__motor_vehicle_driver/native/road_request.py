"""Authored divided-road U-turn requests for the frozen C82860 cell.

The two requests share a road and controller path shape. Their crossing x
coordinate is the only deliberate comparison difference. Public authority is
an original source question and is never inferred from this road geometry.
"""

from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET


ASSIGNMENT = "training__C82860__NRS-484B-227-1__motor_vehicle_driver"
ROAD_IDS = (828601, 828602)
CAMERAS = (
    ("overview", 1920, 1080),
    ("approach", 1280, 720),
    ("median_reference", 1280, 720),
    ("driver_reference", 1280, 720),
)


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C82860-divided-median", version="1", north="20",
                  south="-20", east="70", west="-70", vendor="worker-authored")
    for road_id, name, x, y, heading in (
        (ROAD_IDS[0], "eastbound_right_hand_roadway", -70, -5, 0),
        (ROAD_IDS[1], "westbound_right_hand_roadway", 70, 5, math.pi),
    ):
        road = ET.SubElement(root, "road", id=str(road_id), name=name,
                             length="140", junction="-1")
        ET.SubElement(road, "link")
        view = ET.SubElement(road, "planView")
        ET.SubElement(ET.SubElement(view, "geometry", s="0", x=str(x),
                                    y=str(y), hdg=str(heading), length="140"), "line")
        profile = ET.SubElement(road, "elevationProfile")
        ET.SubElement(profile, "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        ET.SubElement(ET.SubElement(section, "center"), "lane", id="0",
                      type="none", level="false")
        lane = ET.SubElement(ET.SubElement(section, "right"), "lane", id="-1",
                             type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        objects = ET.SubElement(road, "objects")
        if road_id == ROAD_IDS[0]:
            for index, start in enumerate((-20, 3), 1):
                ET.SubElement(objects, "object", id=str(index),
                              name=f"median_dividing_section_{index}",
                              type="barrier", s=str(start + 70), t="5",
                              zOffset="0", hdg="0", pitch="0", roll="0",
                              length="17", width="4", height="0.25")
        ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(crossing):
    if crossing not in ("authorized_opening", "barrier_crossing"):
        raise ValueError("unknown exact crossing request")
    x = 0 if crossing == "authorized_opening" else 10
    return {
        "format": "worker-authored-divided-uturn-request",
        "assignment_id": ASSIGNMENT,
        "case_id": ASSIGNMENT + "__" + crossing,
        "cell_id": "C82860", "actor": "motor_vehicle_driver",
        "layout": "divided_road", "maneuver": "u_turn",
        "source_map": road_xml(),
        "road_ids": list(ROAD_IDS),
        "ego_blueprint": "vehicle.tesla.model3",
        "start_xyz_m": [-25, -6.75, 1.5],
        "route_waypoints_xy_m": [[-25, -6.75], [x - 5, -6.75], [x, -6.75],
                                  [x, 0], [x, 6.75], [x - 5, 6.75]],
        "requested_crossing_x_m": x,
        "median_bounds_m": [-20, -2, 20, 2],
        "opening_bounds_m": [-3, -2, 3, 2],
        "barrier_bounds_m": [[-20, -2, -3, 2], [3, -2, 20, 2]],
        "public_authority_establishment": "pending_original_source",
        "physical_realization": "unverified",
        "rate_hz": 20, "duration_s": 30, "frames": 600,
        "cameras": [{"name": n, "width": w, "height": h} for n, w, h in CAMERAS],
        "legal_verdict": None,
    }


def check(first, second):
    expected = ("authorized_opening", "barrier_crossing")
    for case, item in zip(expected, (first, second)):
        if item != request(case):
            raise ValueError("exact U-turn request differs: " + case)
        root = ET.fromstring(item["source_map"])
        roads = root.findall("road")
        if [int(road.attrib["id"]) for road in roads] != list(ROAD_IDS):
            raise ValueError("both opposing Native roadways required")
        names = [obj.attrib["name"] for obj in root.findall(".//object")]
        if names != ["median_dividing_section_1", "median_dividing_section_2"]:
            raise ValueError("physical median sections and opening required")
    if first["requested_crossing_x_m"] == second["requested_crossing_x_m"]:
        raise ValueError("comparison crossing location not varied")
    return {"passed": True, "physical_native_verified": False,
            "authority_verified": False, "cases": [x["case_id"] for x in (first, second)]}


def write(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cases = [request("authorized_opening"), request("barrier_crossing")]
    check(*cases)
    for item in cases:
        suffix = item["case_id"].split("__")[-1]
        (directory / (suffix + ".json")).write_text(json.dumps(item, indent=2) + "\n")
    return cases


if __name__ == "__main__":
    write(Path(__file__).resolve().parent / "requests")
