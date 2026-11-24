"""Exact unselected sidewalk-stop construction and post-tick source packet."""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ASSIGNMENT = "training__C229977__NRS-484B-450-1a__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "sidewalk_boundary", "driver_reference")
HERE = Path(__file__).resolve().parent


def request(frame, case_id):
    if type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("frame outside 600-frame contract")
    if case_id not in (ASSIGNMENT + "__probe_1", ASSIGNMENT + "__probe_2"):
        raise ValueError("unknown exact case")
    sidewalk = case_id.endswith("probe_2")
    return {"target_speed_mps": 0.0 if 160 <= frame < 500 else 4.0,
            "target_lateral_m": -5.0 if sidewalk else -1.75,
            "requested_sidewalk_occupancy": sidewalk}


def capture_row(index, native_frame, elapsed_s, actor):
    if type(index) is not int or not 0 <= index < 600 or type(native_frame) is not int:
        raise ValueError("original frame identity required")
    if not isinstance(elapsed_s, (float, int)) or not math.isfinite(elapsed_s):
        raise ValueError("original Native time required")
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(pose)
    if len(vertices) != 8:
        raise ValueError("original vehicle body required")
    return {"frame": index, "native_frame": native_frame, "time_s": elapsed_s,
            "actor_id": actor.id, "blueprint_id": actor.type_id,
            "actor_pose_source": "native_post_tick", "velocity_source": "native_post_tick",
            "speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
            "body_vertices_m": [[v.x, v.y, v.z] for v in vertices]}


def check(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-450-1a", "C229977", "motor_vehicle_driver"):
        raise ValueError("frozen identity differs")
    case = config.get("case_id")
    if case not in (ASSIGNMENT + "__probe_1", ASSIGNMENT + "__probe_2"):
        raise ValueError("case identity differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("30-second timing differs")
    if [c["name"] for c in config.get("cameras", [])] != list(CAMERAS):
        raise ValueError("four-camera profile differs")
    root = ET.parse(HERE / "road.xodr").getroot()
    road = root.find("road")
    if road is None or road.get("id") != "1" or road.get("length") != "100":
        raise ValueError("authored highway absent")
    lane = root.find(".//lane[@id='-2']")
    if lane is None or lane.get("type") != "sidewalk" or float(lane.find("width").get("a")) != 3:
        raise ValueError("authored sidewalk lane absent")
    intended = -5.0 if case.endswith("probe_2") else -1.75
    if request(200, case)["target_lateral_m"] != intended:
        raise ValueError("controlled sidewalk target differs")
    return {"passed": True, "case_id": case, "frames": 600, "rate_hz": 20,
            "cameras": list(CAMERAS), "sidewalk_lane_id": -2,
            "native_capture_implemented": False, "physical_observation_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Native CARLA orchestration remains unfinished")
    print(json.dumps(check(json.loads((HERE / "config.json").read_text())), sort_keys=True))
