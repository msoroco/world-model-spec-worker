"""Two controlled emergency-approach requests for the frozen road/travel cell.

The scene is a Native acquisition hypothesis. It does not establish that the
vehicle is legally authorized or that its lamps meet NRS 484A.480(3).
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET


ASSIGNMENT = "training__C405647__NRS-484B-267-2c__motor_vehicle_driver"
CASES = ("braking_capacity_available", "not_available")
CAMERAS = (
    ("overview", 1920, 1080),
    ("approach", 1280, 720),
    ("reference_corner", 1280, 720),
    ("driver_reference", 1280, 720),
)
CAMERA_DIMENSIONS = {name: (width, height) for name, width, height in CAMERAS}


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C405647-emergency-approach", version="1",
                  north="20", south="-20", east="110", west="-110",
                  vendor="worker-authored")
    road = ET.SubElement(root, "road", id="405647", name="travel-and-shoulder",
                         length="200", junction="-1")
    ET.SubElement(road, "link")
    view = ET.SubElement(road, "planView")
    ET.SubElement(ET.SubElement(view, "geometry", s="0", x="-100",
                                y="0", hdg="0", length="200"), "line")
    profile = ET.SubElement(road, "elevationProfile")
    ET.SubElement(profile, "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0",
                  type="none", level="false")
    right = ET.SubElement(section, "right")
    for ident, kind, width in (("-1", "driving", "3.5"),
                               ("-2", "shoulder", "3.0")):
        lane = ET.SubElement(right, "lane", id=ident, type=kind,
                             level="false")
        ET.SubElement(lane, "width", sOffset="0", a=width, b="0", c="0", d="0")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(condition):
    if condition not in CASES:
        raise ValueError("Unknown exact emergency-approach condition")
    return {
        "format": "c405647-native-scene-request-v1",
        "assignment_id": ASSIGNMENT,
        "case_id": ASSIGNMENT + "__" + condition,
        "law_id": "NRS-484B-267-2c", "cell_id": "C405647",
        "actor": "motor_vehicle_driver", "layout": "road",
        "maneuver": "travel", "control": "emergency_vehicle",
        "source_map": road_xml(), "road_id": 405647,
        "ego_blueprint": "vehicle.tesla.model3",
        "emergency_blueprint": "vehicle.dodge.charger_police",
        "ego_start_xyz_m": [-80, -1.75, 1.5],
        "ego_cruise_speed_mps": 5.0,
        "emergency_start_xyz_m": [15, -5.0, 1.5],
        "ego_destination_xy_m": [80, -1.75],
        "emergency_motion_start_frame": 150,
        "emergency_target_speed_mps": 0.5,
        "light_request": "special1_and_special2",
        "light_qualification": "pending_independent_source_review",
        "visible_indication": "pending_original_four_camera_review",
        "officer_direction": "pending_independent_source_review",
        "ego_response_policy": {
            "trigger_frame": 150,
            "brake_onset_frame": 180 if condition == "braking_capacity_available" else None,
            "brake_command": 0.8 if condition == "braking_capacity_available" else 0.0,
        },
        "comparison_variable": "ego_stop_preparedness",
        "requested_setting": condition,
        "physical_risk_assessment": {
            "road_runoff": "Unbraked contrast may reach the east map edge; requested cruise is bounded to 5 m/s but original trajectory must be checked.",
            "camera_visibility": "Four requested views may not show qualifying lamp color and motion throughout the approach; original pixels require review.",
            "subject_qualification": "A CARLA police blueprint and Special1 request do not establish statutory vehicle authorization or lamp compliance.",
            "response_proxy": "Brake actuation and stopping distance are engineering observations, not a legal threshold for prepared to stop."
        },
        "rate_hz": 20, "duration_s": 30, "frames": 600,
        "cameras": [{"name": name, "width": width, "height": height}
                    for name, width, height in CAMERAS],
        "physical_acceptance_claimed": False,
        "legal_verdict": None,
    }


def check_pair(first, second):
    if first != request(CASES[0]) or second != request(CASES[1]):
        raise ValueError("Exact emergency-approach requests changed")
    root = ET.fromstring(first["source_map"])
    lanes = {lane.get("id"): lane.get("type")
             for lane in root.findall(".//lane")}
    if lanes.get("-1") != "driving" or lanes.get("-2") != "shoulder":
        raise ValueError("Travel lane and visible shoulder required")
    if first["emergency_start_xyz_m"][1] >= first["ego_start_xyz_m"][1]:
        raise ValueError("Emergency subject must be beside travel lane")
    fixed = set(first) - {"case_id", "ego_response_policy", "requested_setting"}
    if {key: first[key] for key in fixed} != {key: second[key] for key in fixed}:
        raise ValueError("Non-response comparison context changed")
    if first["ego_response_policy"] == second["ego_response_policy"]:
        raise ValueError("Response policy was not varied")
    return {"passed": True, "exact_cases": [first["case_id"], second["case_id"]],
            "physical_or_legal_acceptance": False}


def write(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pair = [request(condition) for condition in CASES]
    check_pair(*pair)
    for condition, data in zip(CASES, pair):
        (directory / (condition + ".json")).write_text(json.dumps(data, indent=2) + "\n")
    return pair


if __name__ == "__main__":
    print(json.dumps(check_pair(*(request(condition) for condition in CASES))))
