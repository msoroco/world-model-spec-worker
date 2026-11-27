"""Source-gated two-way road plan for NRS 484B.627(1)(a).

All widths and distances are physical observations or engineering requests.
They do not decide impediment, whether pavement permits moving right, or
whether NRS 484B.630 applies.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree


ASSIGNMENT = "testing__C323986__NRS-484B-627-1a__motor_vehicle_driver"
VARIANTS = {
    "slow_center_wide": {"ego_path": "center", "follower": True, "pavement": "wide"},
    "slow_right_wide": {"ego_path": "right", "follower": True, "pavement": "wide"},
    "slow_center_narrow": {"ego_path": "center", "follower": True, "pavement": "narrow"},
    "slow_center_no_follower": {"ego_path": "center", "follower": False, "pavement": "wide"},
    "slow_center_obstruction_near": {"ego_path": "center", "follower": True, "pavement": "wide", "obstruction": "near"},
}
for _index in range(3):
    VARIANTS[f"impediment-{_index:04d}"] = {"ego_path": "center", "follower": True, "pavement": "wide"}
    VARIANTS[f"paved_width-{_index:04d}"] = {"ego_path": "center", "follower": True, "pavement": "sweep"}
    VARIANTS[f"right_position-{_index:04d}"] = {"ego_path": "right", "follower": True, "pavement": "wide"}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _source(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
        raise ValueError("original reviewed source reference required")
    candidate = root / ref["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original reviewed source path missing or escaping root")
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("original reviewed source hash changed")
    return path


def plan(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in VARIANTS:
        raise ValueError("unassigned exact case")
    root = Path(authority_root).resolve()
    site_path = _source(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("original reviewed highway site required")
    variants = site.get("variants", {})
    variant = VARIANTS[suffix]
    physical = variants.get(suffix)
    if not isinstance(physical, dict):
        raise ValueError("reviewed case geometry missing")
    base = variants.get("slow_center_wide")
    if not isinstance(base, dict) or set(variants) != set(VARIANTS):
        raise ValueError("all exact comparison site variants required")
    allowed_changes = {
        "slow_center_wide": set(),
        "slow_right_wide": set(),
        "slow_center_narrow": {"paved_right_edge_m", "highway_right_edge_m", "map_ref"},
        "slow_center_no_follower": set(),
        "slow_center_obstruction_near": {"obstruction_station_m", "obstruction_left_edge_m",
                                          "obstruction_right_edge_m"},
    }
    for index in range(3):
        allowed_changes[f"impediment-{index:04d}"] = {"ego_speed_mps"}
        allowed_changes[f"paved_width-{index:04d}"] = {"paved_right_edge_m", "highway_right_edge_m", "map_ref"}
        allowed_changes[f"right_position-{index:04d}"] = {"ego_right_path_m"}
    for name, candidate in variants.items():
        if not isinstance(candidate, dict):
            raise ValueError("reviewed comparison variant malformed")
        changed = {key for key in set(base) | set(candidate) if base.get(key) != candidate.get(key)}
        if not changed <= allowed_changes[name]:
            raise ValueError("reviewed comparison changed held physical facts: " + name)
    map_path = _source(root, physical.get("map_ref", site.get("map_ref")))
    try:
        document = ElementTree.fromstring(map_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise ValueError("reviewed OpenDRIVE map malformed") from error
    roads = [road for road in document.findall("road") if road.get("id") == site.get("road_id")]
    if len(roads) != 1:
        raise ValueError("reviewed road absent from OpenDRIVE")
    lanes = {lane.get("id") for lane in roads[0].findall(".//lane") if lane.get("type") == "driving"}
    travel_lane = site.get("travel_lane_id")
    opposite_lane = site.get("opposite_lane_id")
    if (site.get("highway") is not True or site.get("one_lane_each_direction") is not True or
            len(lanes) != 2 or
            travel_lane not in lanes or opposite_lane not in lanes or travel_lane == opposite_lane or
            site.get("opposite_direction_verified") is not True):
        raise ValueError("one lane each direction not source verified")
    for key in ("paved_right_edge_m", "highway_right_edge_m", "obstruction_right_edge_m",
                "obstruction_left_edge_m", "ego_center_path_m", "ego_right_path_m",
                "ego_half_width_m", "follower_start_station_m", "ego_start_station_m",
                "ego_speed_mps", "follower_speed_mps", "obstruction_station_m"):
        if not _finite(physical.get(key)):
            raise ValueError("source-reviewed physical geometry or controls missing: " + key)
    if not isinstance(physical.get("obstruction_blueprint_id"), str) or not physical["obstruction_blueprint_id"].startswith("static.prop."):
        raise ValueError("source-reviewed physical obstruction blueprint missing")
    if (physical["ego_half_width_m"] <= 0 or physical["ego_speed_mps"] <= 0 or
            physical["follower_speed_mps"] <= 0 or
            physical["follower_start_station_m"] >= physical["ego_start_station_m"] or
            physical["obstruction_left_edge_m"] >= physical["obstruction_right_edge_m"] or
            physical["paved_right_edge_m"] > physical["highway_right_edge_m"]):
        raise ValueError("source-reviewed actor order or road geometry infeasible")
    ego_offset = physical["ego_right_path_m"] if variant["ego_path"] == "right" else physical["ego_center_path_m"]
    cameras = site.get("camera_profiles", {})
    if set(cameras) != set(CAMERAS):
        raise ValueError("four reviewed camera profiles required")
    expected_sizes = {"overview": (1920, 1080), "approach": (1280, 720),
                      "reference_corner": (1280, 720),
                      "driver_reference": (1280, 720)}
    for name, profile in cameras.items():
        pose = profile.get("pose") if isinstance(profile, dict) else None
        if (not isinstance(pose, dict) or
                (profile.get("width"), profile.get("height")) != expected_sizes[name] or
                not _finite(profile.get("fov_deg")) or not 1 < profile["fov_deg"] < 179 or
                any(not _finite(pose.get(k)) for k in ("x", "y", "z", "pitch", "yaw", "roll"))):
            raise ValueError("reviewed camera profile missing")
    # A path requested at a right-side offset is only a target. Native motion,
    # footprint clearance and body position are checked from original samples.
    return {
        "format": "c323986-reviewed-two-way-plan-v1", "case_id": case_id,
        "site_sha256": site_ref["sha256"], "map_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
        "map_path": str(map_path), "road_id": site["road_id"],
        "travel_lane_id": travel_lane, "opposite_lane_id": opposite_lane,
        "paved_right_edge_m": physical["paved_right_edge_m"],
        "highway_right_edge_m": physical["highway_right_edge_m"],
        "obstruction_lateral_edges_m": [physical["obstruction_left_edge_m"], physical["obstruction_right_edge_m"]],
        "obstruction_station_m": physical["obstruction_station_m"],
        "obstruction_blueprint_id": physical["obstruction_blueprint_id"],
        "ego_half_width_m": physical["ego_half_width_m"],
        "actors": [
            {"role": "ego", "lane_id": travel_lane, "station_m": physical["ego_start_station_m"],
             "lateral_offset_m": ego_offset, "target_speed_mps": physical["ego_speed_mps"]},
            {"role": "following_vehicle", "lane_id": travel_lane if variant["follower"] else opposite_lane,
             "station_m": physical["follower_start_station_m"], "lateral_offset_m": physical["ego_center_path_m"],
             "target_speed_mps": physical["follower_speed_mps"],
             "requested_immediately_behind": variant["follower"]},
        ],
        "cameras": cameras, "hz": 20, "frames": 900,
        "requested_pavement_variant": variant["pavement"],
        "requested_obstruction_variant": variant.get("obstruction", "far"),
        "physical_acceptance": False, "legal_verdict": None,
    }


def execute_native(scene: dict, adapter: object) -> dict:
    if scene.get("format") != "c323986-reviewed-two-way-plan-v1":
        raise ValueError("reviewed two-way scene required")
    adapter.open_map(scene["map_path"], scene["map_sha256"])
    obstacle = adapter.spawn_obstruction(
        road_id=scene["road_id"], lane_id=scene["travel_lane_id"],
        station_m=scene["obstruction_station_m"],
        lateral_edges_m=scene["obstruction_lateral_edges_m"],
        blueprint_id=scene["obstruction_blueprint_id"])
    actors = {}
    for spec in scene["actors"]:
        actors[spec["role"]] = adapter.spawn_vehicle(**spec)
    cameras = {name: adapter.attach_camera(name=name, ego=actors["ego"], profile=profile)
               for name, profile in scene["cameras"].items()}
    for frame in range(scene["frames"]):
        adapter.tick_and_capture(frame=frame, hz=scene["hz"], actors=actors,
                                 cameras=cameras, obstruction=obstacle, scene=scene)
    return {"case_id": scene["case_id"], "frames_requested": scene["frames"],
            "obstruction": obstacle, "physical_acceptance": False}
