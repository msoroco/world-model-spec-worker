"""Build a reproducible engineering scene for the first median-opening case.

The map and prop asset are candidates. This script makes no public-authority,
Native asset, or realized-motion claim.
"""
from __future__ import annotations

import hashlib
import json
import math
import copy
from pathlib import Path
from xml.etree import ElementTree as ET

from case_builder import config
from runner import check_scene


HERE = Path(__file__).resolve().parent
CASE = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening_single"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> str:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    return sha(data)


def road(root: ET.Element, road_id: int, x: float, y: float, heading: float,
         left_driving: bool = False, length: float = 80) -> None:
    item = ET.SubElement(root, "road", {"name": f"candidate right roadway {road_id}",
                                        "length": str(length), "id": str(road_id), "junction": "-1"})
    ET.SubElement(item, "link")
    plan = ET.SubElement(item, "planView")
    geometry = ET.SubElement(plan, "geometry", {"s": "0", "x": str(x), "y": str(y),
                                                "hdg": str(heading), "length": str(length)})
    ET.SubElement(geometry, "line")
    elevation = ET.SubElement(item, "elevationProfile")
    ET.SubElement(elevation, "elevation", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    ET.SubElement(item, "lateralProfile")
    lanes = ET.SubElement(item, "lanes")
    ET.SubElement(lanes, "laneOffset", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    if left_driving:
        left = ET.SubElement(section, "left")
        other = ET.SubElement(left, "lane", {"id": "1", "type": "driving", "level": "false"})
        ET.SubElement(other, "width", {"sOffset":"0", "a":"3.5", "b":"0", "c":"0", "d":"0"})
        ET.SubElement(other, "roadMark", {"sOffset":"0", "type":"solid",
                                          "weight":"standard", "color":"yellow",
                                          "width":"0.12", "laneChange":"none"})
    right = ET.SubElement(section, "right")
    drive = ET.SubElement(right, "lane", {"id": "-1", "type": "driving", "level": "false"})
    ET.SubElement(drive, "width", {"sOffset": "0", "a": "3.5", "b": "0", "c": "0", "d": "0"})
    ET.SubElement(drive, "roadMark", {"sOffset": "0", "type": "solid", "weight": "standard",
                                      "color": "white", "width": "0.12", "laneChange": "none"})


def build() -> dict:
    root = ET.Element("OpenDRIVE")
    header = ET.SubElement(root, "header", {"revMajor": "1", "revMinor": "4",
                                            "name": "C126120 engineering median opening",
                                            "version": "1", "north": "10", "south": "-10",
                                            "east": "40", "west": "-40", "vendor": "worker-candidate"})
    ET.SubElement(header, "geoReference").text = (
        "+proj=tmerc +lat_0=0 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    road(root, 10, -40, -4, 0)
    road(root, 20, 40, 4, math.pi, left_driving=True)
    map_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    map_path = HERE / "candidate-median-opening.xodr"
    map_path.write_bytes(map_bytes)
    authority = {"source_kind": "local engineering candidate",
                 "public_authority_establishment": "unverified",
                 "reviewed_administrative_record": None,
                 "legal_effect_claimed": False}
    authority_hash = write_json(HERE / "candidate-authority-review.json", authority)
    barriers = [[-12, -.25, -4.2, .25], [4.2, -.25, 12, .25]]
    props = []
    for start in (-12, 4.2):
        for index in range(4):
            left = round(start + index*1.95, 3)
            props.append({"blueprint_id": "static.prop.streetbarrier",
                          "bounds_xy_m": [left, -.25, round(left+1.95, 3), .25],
                          "z_m": 0.0})
    context = {"opening_id": "candidate-opening-1",
               "opening_bounds_xy_m": [-4, -3, 4, 3],
               "closed_divider_bounds_xy_m": barriers,
               "source_right_roadway_id": "candidate-road-10-right",
               "destination_right_roadway_id": "candidate-road-20-right",
               "source_right_roadway_bounds_xy_m": [-20, -8, 20, -2],
               "destination_right_roadway_bounds_xy_m": [-20, 4, 20, 8],
               "opposite_non_right_roadway_bounds_xy_m": [-20, 1, 20, 4],
               "map_source_sha256": sha(map_bytes),
               "authority_review_source_sha256": authority_hash}
    reviewed = {"source_kind": "local engineering candidate",
                "review_status": "CPU geometry checked; live map and Native prop footprint unverified",
                "map_source": map_path.name,
                "context": context, "divider_props": props}
    reviewed_hash = write_json(HERE / "candidate-reviewed-median.json", reviewed)
    scene = {"case_id": CASE, "map_source": map_path.name,
             "vehicle_blueprint_id": "vehicle.tesla.model3",
             "reviewed_context_source": "candidate-reviewed-median.json",
             "reviewed_context_sha256": reviewed_hash,
             "authority_review_source": "candidate-authority-review.json",
             "context": context, "divider_props": props,
             "route_xy_m": [[-8,-5.75],[-4,-5.75],[-1,-4],[1,-1],[1,1],[-1,4],[-4,5.75],[-8,5.75]],
             "segment_directions": ["forward"]*7,
             "vehicle_half_width_m": 1.0,
             "source_road_id": 10, "source_lane_id": -1,
             "destination_road_id": 20, "destination_lane_id": -1,
             "capture_rate_hz": 20, "duration_s": 30}
    check_scene(scene)
    write_json(HERE / "scene.json", scene)
    write_json(HERE / "config.json", config(scene))
    multiple = dict(scene)
    multiple["case_id"] = CASE.replace("__opening_single", "__opening_multiple")
    multiple["route_xy_m"] = [
        [-8,-5.75],[-4,-5.75],[-1,-4],[1,-1],[1.5,-1],
        [.5,-1],[1,1],[-1,4],[-4,5.75],[-8,5.75]]
    multiple["segment_directions"] = ["forward"]*4+["reverse"]+["forward"]*4
    multiple["reviewed_context_source"] = "../../candidate-reviewed-median.json"
    multiple["authority_review_source"] = "../../candidate-authority-review.json"
    multiple["map_source"] = "../../candidate-median-opening.xodr"
    check_scene(multiple)
    multiple_dir = HERE / "cases" / "opening_multiple"
    multiple_dir.mkdir(parents=True, exist_ok=True)
    write_json(multiple_dir / "scene.json", multiple)
    write_json(multiple_dir / "config.json", config(multiple))
    closed = dict(scene)
    closed["case_id"] = CASE.replace("__opening_single", "__closed_divider")
    closed["physical_target"] = "closed_divider_approach"
    closed["vehicle_half_length_m"] = 2.5
    closed["route_xy_m"] = [[-18,-5.75],[-14,-5.75],[-10,-5.75],[-8,-4],[-8,-3]]
    closed["segment_directions"] = ["forward"]*4
    closed["reviewed_context_source"] = "../../candidate-reviewed-median.json"
    closed["authority_review_source"] = "../../candidate-authority-review.json"
    closed["map_source"] = "../../candidate-median-opening.xodr"
    check_scene(closed)
    closed_dir = HERE / "cases" / "closed_divider"
    closed_dir.mkdir(parents=True, exist_ok=True)
    write_json(closed_dir / "scene.json", closed)
    write_json(closed_dir / "config.json", config(closed))
    wrong = dict(scene)
    wrong["case_id"] = CASE.replace("__opening_single", "__wrong_roadway")
    wrong["physical_target"] = "non_right_roadway"
    wrong["destination_lane_id"] = 1
    wrong["route_xy_m"] = [[-8,-5.75],[-4,-5.75],[-1,-4],[1,-1],[1,1],
                           [-1,2.25],[-4,2.25],[-8,2.25]]
    wrong["segment_directions"] = ["forward"]*7
    wrong["reviewed_context_source"] = "../../candidate-reviewed-median.json"
    wrong["authority_review_source"] = "../../candidate-authority-review.json"
    wrong["map_source"] = "../../candidate-median-opening.xodr"
    check_scene(wrong)
    wrong_dir = HERE / "cases" / "wrong_roadway"
    wrong_dir.mkdir(parents=True, exist_ok=True)
    write_json(wrong_dir / "scene.json", wrong)
    write_json(wrong_dir / "config.json", config(wrong))
    no_turn = dict(scene)
    no_turn["case_id"] = CASE.replace("__opening_single", "__right_roadway_no_turn")
    no_turn["physical_target"] = "source_right_roadway_continuation"
    no_turn["destination_road_id"] = 10
    no_turn["route_xy_m"] = [[-18,-5.75],[-14,-5.75],[-10,-5.75],
                              [-6,-5.75],[-2,-5.75],[2,-5.75]]
    no_turn["segment_directions"] = ["forward"]*5
    no_turn["reviewed_context_source"] = "../../candidate-reviewed-median.json"
    no_turn["authority_review_source"] = "../../candidate-authority-review.json"
    no_turn["map_source"] = "../../candidate-median-opening.xodr"
    check_scene(no_turn)
    no_turn_dir = HERE / "cases" / "right_roadway_no_turn"
    no_turn_dir.mkdir(parents=True, exist_ok=True)
    write_json(no_turn_dir / "scene.json", no_turn)
    write_json(no_turn_dir / "config.json", config(no_turn))
    special_cases = {}
    for kind in ("crossover_candidate", "intersection_candidate"):
        candidate_root = copy.deepcopy(root)
        if kind == "crossover_candidate":
            road(candidate_root, 30, -1.75, -4, math.pi/2, length=8)
        else:
            road(candidate_root, 31, -1.75, -10, math.pi/2, length=20)
            junction = ET.SubElement(candidate_root,"junction",
                                     {"name":"candidate geometric cross street",
                                      "id":"1"})
            ET.SubElement(junction,"userData",{"code":"review_status",
                                                "value":"topology and authority unverified"})
        special_map = f"candidate-{kind.replace('_','-')}.xodr"
        special_bytes = ET.tostring(candidate_root,encoding="utf-8",xml_declaration=True)
        (HERE/special_map).write_bytes(special_bytes)
        special_context = dict(context)
        special_context["opening_id"] = "candidate-"+kind.replace("_","-")
        special_context["map_source_sha256"] = sha(special_bytes)
        special_context["crossing_kind"] = kind
        special_reviewed = dict(reviewed)
        special_reviewed["context"] = special_context
        special_reviewed["map_source"] = special_map
        special_reviewed["review_status"] = (
            "CPU geometric candidate; live Native topology and public authority unverified")
        special_review_name = f"candidate-reviewed-{kind.replace('_','-')}.json"
        special_hash = write_json(HERE/special_review_name,special_reviewed)
        special_scene = dict(scene)
        special_scene["case_id"] = CASE.replace("__opening_single","__"+kind)
        special_scene["map_source"] = "../../"+special_map
        special_scene["reviewed_context_source"] = "../../"+special_review_name
        special_scene["reviewed_context_sha256"] = special_hash
        special_scene["authority_review_source"] = "../../candidate-authority-review.json"
        special_scene["context"] = special_context
        special_scene["route_xy_m"] = [[-8,-5.75],[-4,-5.75],[-1,-4],
                                        [0,-2],[0,0],[0,2],[-1,4],[-4,5.75],[-8,5.75]]
        special_scene["segment_directions"] = ["forward"]*8
        check_scene(special_scene)
        target_dir = HERE/"cases"/kind
        target_dir.mkdir(parents=True,exist_ok=True)
        write_json(target_dir/"scene.json",special_scene)
        write_json(target_dir/"config.json",config(special_scene))
        special_cases[kind] = special_scene["case_id"]
    return {"case_id": CASE, "map_sha256": context["map_source_sha256"],
            "reviewed_context_sha256": reviewed_hash,
            "authority_review_source_sha256": authority_hash,
            "multiple_movement_case_id": multiple["case_id"],
            "closed_divider_case_id": closed["case_id"],
            "wrong_roadway_case_id": wrong["case_id"],
            "right_roadway_no_turn_case_id": no_turn["case_id"],
            **{kind+"_case_id":case_id for kind,case_id in special_cases.items()},
            "native_verified": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
