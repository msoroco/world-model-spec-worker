"""Four exact green-arrow bus scene drafts on one same-cell engineering road."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
SIBLING_MAP = ROOT.parent / "testing__C147332__NRS-484B-307-12b__bus_driver" / "candidate-red-x-road.xodr"
MAP = ROOT / "candidate-green-road.xodr"
KINDS = ("green_selected_drive", "adjacent_dark_drive", "second_green_drive",
         "green_selected_stand")
LANES = {"east": {"road_lane_id": -1, "center_y_m": -1.8, "bounds_m": [-3.6, 0.0]},
         "west": {"road_lane_id": -2, "center_y_m": -5.4, "bounds_m": [-7.2, -3.6]}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_map(path):
    root = ET.parse(path).getroot()
    roads = root.findall("road")
    if len(roads) != 1 or roads[0].get("id") != "147332" or float(roads[0].get("length", 0)) != 90:
        raise ValueError("wrong same-cell one-way engineering road")
    lanes = roads[0].findall("./lanes/laneSection/right/lane")
    if {int(lane.get("id")) for lane in lanes} != {-1, -2}:
        raise ValueError("two same-direction right-side lanes required")
    if any(lane.get("type") != "driving" or float(lane.find("width").get("a")) != 3.6
           for lane in lanes):
        raise ValueError("lane width/type differs from bus route contract")
    if roads[0].findall("./lanes/laneSection/left/lane"):
        raise ValueError("counterflow lane in one-way scene")
    return sha(path)


def scene(kind, map_sha):
    if kind not in KINDS:
        raise ValueError("unknown exact green-arrow case")
    lane = "west" if kind in ("adjacent_dark_drive", "second_green_drive") else "east"
    x_positions = [8.0, 45.0, 82.0]
    if kind == "green_selected_stand":
        x_positions = [8.0, 8.0, 8.0]
    centers = [[x, LANES[lane]["center_y_m"]] for x in x_positions]
    indicated = ["east", "west"] if kind == "second_green_drive" else ["east"]
    return {"assignment_id": ROOT.name, "case_id": ROOT.name + "__" + kind,
            "law_id": "NRS-484B-307-12a", "cell_id": "C147332", "actor": "bus_driver",
            "layout": "one_way_multilane", "control": "lane_signal",
            "bus_blueprint_id": "vehicle.mitsubishi.fusorosa",
            "bus_lane_id": lane, "bus_half_width_m": 1.25,
            "route_waypoint_centers_m": centers,
            "map_source": "road.xodr", "map_source_sha256": map_sha,
            "signals": [{"placement": "over_individual_lanes", "facing": "bus_approach",
                         "governed_lane_id": key, "road_lane_id": value["road_lane_id"],
                         "lateral_bounds_m": value["bounds_m"],
                         "longitudinal_m": 50.0, "lateral_m": value["center_y_m"],
                         "height_m": 6.0,
                         "display": "down_green_arrow" if key in indicated else "dark",
                         "official_device_source": None}
                        for key, value in LANES.items()],
            "source_requirements": ["original highway source", "original official device record",
                                    "original signal-lane alignment", "original bus footprint"],
            "capture_plan": {"rate_hz": 20, "duration_s": 18,
                             "cameras": ["overview", "approach", "reference_corner",
                                         "driver_reference"]},
            "preparation_status": "engineering_draft_requires_reviewed_source_and_native_binding",
            "legal_judgment": "unresolved"}


def check_scene(value, map_path):
    kind = value.get("case_id", "").removeprefix(ROOT.name + "__")
    if value != scene(kind, check_map(map_path)):
        raise ValueError("exact green-arrow scene or map bytes changed")
    for x, y in value["route_waypoint_centers_m"]:
        if not (0 <= x <= 90 and -7.2 + 1.25 < y < -1.25):
            raise ValueError("full bus width leaves same-direction road")
    return value


def build():
    source = SIBLING_MAP.read_text()
    candidate = source.replace("C147332 red-X engineering candidate",
                               "C147332 green-arrow engineering candidate")
    if not MAP.is_file() or MAP.read_text() != candidate:
        MAP.write_text(candidate)
    map_sha = check_map(MAP)
    paths = []
    for kind in KINDS:
        value = scene(kind, map_sha)
        check_scene(value, MAP)
        path = ROOT / "cases" / kind / "scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        paths.append(path)
    return paths


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(ROOT))
