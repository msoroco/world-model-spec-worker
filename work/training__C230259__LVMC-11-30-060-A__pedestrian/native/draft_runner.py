"""Unselected outside-crosswalk Native request; --check is CPU-only."""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ASSIGNMENT = "training__C230259__LVMC-11-30-060-A__pedestrian"
CAMERAS = ("overview", "pedestrian_entry", "vehicle_approach", "roadway_crossing")
HERE = Path(__file__).resolve().parent


def request(index, case_id):
    if type(index) is not int or not 0 <= index < 600:
        raise ValueError("outside 600-frame contract")
    if case_id not in (ASSIGNMENT + "__probe_01", ASSIGNMENT + "__probe_02"):
        raise ValueError("unknown exact case")
    depart = 320 if case_id.endswith("probe_01") else 140
    return {"pedestrian_departure_frame": depart,
            "pedestrian_target_speed_mps": 1.2 if index >= depart else 0.0,
            "vehicle_target_speed_mps": 2.2,
            "vehicle_yield_command": None,
            "crossing_y_m": 10.0}


def post_tick_row(index, native_frame, elapsed_s, pedestrian, vehicles):
    if type(index) is not int or not 0 <= index < 600 or type(native_frame) is not int:
        raise ValueError("original frame identity required")
    if type(elapsed_s) not in (int, float) or not math.isfinite(elapsed_s):
        raise ValueError("original time required")
    pose = pedestrian.get_transform()
    points = sorted({(round(v.x, 5), round(v.y, 5))
                     for v in pedestrian.bounding_box.get_world_vertices(pose)})
    if len(points) != 4:
        raise ValueError("original pedestrian footprint required")
    observed = []
    for vehicle in vehicles:
        vpose, velocity = vehicle.get_transform(), vehicle.get_velocity()
        observed.append({"id": vehicle.id, "x_m": vpose.location.x,
                         "y_m": vpose.location.y,
                         "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)})
    return {"native_frame": native_frame, "time_s": elapsed_s,
            "pedestrian_id": pedestrian.id, "pedestrian_footprint_xy_m": [list(v) for v in points],
            "vehicles": observed, "source": "native_post_tick"}


def check(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-30-060-A", "C230259", "pedestrian"):
        raise ValueError("frozen identity differs")
    case = config.get("case_id")
    if case not in (ASSIGNMENT + "__probe_01", ASSIGNMENT + "__probe_02"):
        raise ValueError("exact case differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("30-second timing differs")
    if [c.get("name") for c in config.get("cameras", [])] != list(CAMERAS):
        raise ValueError("four-camera contract differs")
    root = ET.parse(HERE / "road.xodr").getroot()
    road = root.find("road")
    if road is None or road.get("junction") != "-1" or road.get("length") != "60":
        raise ValueError("authored road geometry differs")
    if root.findall(".//objects/object") or root.findall(".//junction"):
        raise ValueError("draft must omit marked crossing and intersection")
    assert request(0, case)["pedestrian_target_speed_mps"] == 0
    return {"passed": True, "case_id": case, "frames": 600, "rate_hz": 20,
            "cameras": list(CAMERAS), "native_capture_implemented": False,
            "source_meter_interface_implemented": True,
            "physical_crossing_observed": False, "legal_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Native CARLA orchestration remains unfinished")
    print(json.dumps(check(json.loads((HERE / "config.json").read_text())), sort_keys=True))
