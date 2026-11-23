"""Check the authored blind-junction candidate before Native construction.

The map and geometry checks are CPU preparation. Native actor placement,
camera visibility, and physical signal behavior require later source review.
"""

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from shapely.geometry import LineString, Polygon


def _point(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("Finite XY point required")
    return value


def validate(candidate_path):
    candidate_path = Path(candidate_path)
    candidate = json.loads(candidate_path.read_text())
    if candidate.get("format") != "c24811-blind-site-candidate-v1":
        raise ValueError("C24811 site candidate required")
    binding = candidate["map"]
    if set(binding) != {"path", "sha256"} or Path(binding["path"]).name != binding["path"]:
        raise ValueError("Local hashed map binding required")
    map_path = candidate_path.parent / binding["path"]
    if hashlib.sha256(map_path.read_bytes()).hexdigest() != binding["sha256"]:
        raise ValueError("Authored map changed")
    root = ET.parse(map_path).getroot()
    if root.tag != "OpenDRIVE":
        raise ValueError("OpenDRIVE map required")
    junction_id = candidate["junction_id"]
    if root.find(f"junction[@id='{junction_id}']") is None:
        raise ValueError("Authored junction missing")
    roads = {int(r.get("id")): r for r in root.findall("road")}
    entrances = candidate["entrances"]
    if set(entrances) != {"ego", "other"}:
        raise ValueError("Two governed entrances required")
    ids = []
    for name, entry in entrances.items():
        road = roads.get(entry["road_id"])
        if road is None:
            raise ValueError("Approach road missing")
        signals = [s for s in road.findall("signals/signal")
                   if s.get("id") == str(entry["map_signal_id"]) and
                   s.find("validity") is not None and
                   int(s.find("validity").get("fromLane")) <= entry["lane_id"] <=
                   int(s.find("validity").get("toLane"))]
        if len(signals) != 1:
            raise ValueError("Governed signal missing or ambiguous: " + name)
        marks = [o for o in road.findall("objects/object")
                 if o.get("id") == str(entry["stop_line_object_id"]) and
                 o.get("name") == "StopLine"]
        if len(marks) != 1:
            raise ValueError("Marked stop line missing: " + name)
        _point(entry["viewpoint_xy_m"])
        _point(entry["target_vehicle_xy_m"])
        if entry["viewpoint_xy_m"] == entry["target_vehicle_xy_m"]:
            raise ValueError("Zero sight ray")
        ids.append(entry["map_signal_id"])
    if len(set(ids)) != 2:
        raise ValueError("Distinct signal IDs required")
    footprint = Polygon([_point(p) for p in candidate["occluder"]["planned_footprint_xy_m"]])
    if not footprint.is_valid or footprint.area <= 0:
        raise ValueError("Valid occluder footprint required")
    clearance = candidate["occluder"]["minimum_corridor_clearance_m"]
    if type(clearance) not in (int, float) or clearance < 1:
        raise ValueError("Positive engineering clearance required")
    hits = {}
    for name, entry in entrances.items():
        ray = LineString([entry["viewpoint_xy_m"], entry["target_vehicle_xy_m"]])
        hits[name] = ray.intersects(footprint)
        if not hits[name]:
            raise ValueError("Planned occluder misses sight ray: " + name)
        corridor = LineString([_point(p) for p in entry["vehicle_corridor_centerline_xy_m"]])
        if footprint.distance(corridor) < clearance:
            raise ValueError("Planned occluder intrudes on vehicle corridor: " + name)
    return {"map_sha256": binding["sha256"], "junction_id": junction_id,
            "planned_sight_ray_intersections": hits,
            "planned_corridor_clearance_m": {name: round(footprint.distance(
                LineString(entry["vehicle_corridor_centerline_xy_m"])), 3)
                for name, entry in entrances.items()},
            "native_visibility_verified": False, "physical_acceptance": False}


if __name__ == "__main__":
    print(json.dumps(validate(Path(__file__).with_name("blind-site-candidate.json")), indent=2))
