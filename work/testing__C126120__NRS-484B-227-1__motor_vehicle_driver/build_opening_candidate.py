"""Build a reproducible engineering scene for the first median-opening case.

The map and prop asset are candidates. This script makes no public-authority,
Native asset, or realized-motion claim.
"""
from __future__ import annotations

import hashlib
import json
import math
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


def road(root: ET.Element, road_id: int, x: float, y: float, heading: float) -> None:
    item = ET.SubElement(root, "road", {"name": f"candidate right roadway {road_id}",
                                        "length": "80", "id": str(road_id), "junction": "-1"})
    ET.SubElement(item, "link")
    plan = ET.SubElement(item, "planView")
    geometry = ET.SubElement(plan, "geometry", {"s": "0", "x": str(x), "y": str(y),
                                                "hdg": str(heading), "length": "80"})
    ET.SubElement(geometry, "line")
    elevation = ET.SubElement(item, "elevationProfile")
    ET.SubElement(elevation, "elevation", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    ET.SubElement(item, "lateralProfile")
    lanes = ET.SubElement(item, "lanes")
    ET.SubElement(lanes, "laneOffset", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
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
    road(root, 20, 40, 4, math.pi)
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
               "opening_bounds_xy_m": [-4, -.25, 4, .25],
               "closed_divider_bounds_xy_m": barriers,
               "source_right_roadway_id": "candidate-road-10-right",
               "destination_right_roadway_id": "candidate-road-20-right",
               "source_right_roadway_bounds_xy_m": [-20, -8, 20, -2],
               "destination_right_roadway_bounds_xy_m": [-20, 2, 20, 8],
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
             "source_road_id": 10, "destination_road_id": 20,
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
    return {"case_id": CASE, "map_sha256": context["map_source_sha256"],
            "reviewed_context_sha256": reviewed_hash,
            "authority_review_source_sha256": authority_hash,
            "multiple_movement_case_id": multiple["case_id"],
            "native_verified": False}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
