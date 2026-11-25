"""Source-gated four-case Native scene plan for NRS 484B.627(1)(b).

The reviewed site packet supplies geometry and feasible speed controls. A plan
is a request for local CARLA construction, never a legal or physical finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree


ASSIGNMENT = "testing__C147344__NRS-484B-627-1b__motor_vehicle_driver"
VARIANTS = {
    "slow_middle_follower": ("middle", True, False),
    "slow_right_follower": ("right", True, False),
    "slow_middle_passing": ("middle", True, True),
    "slow_middle_no_immediate_follower": ("middle", False, False),
}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _linked(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
        raise ValueError("reviewed source reference missing")
    candidate = root / ref["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("reviewed source path missing or escaping root")
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("reviewed source hash changed")
    return path


def _finite_positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def plan(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in VARIANTS:
        raise ValueError("unassigned exact construction case")
    root = Path(authority_root).resolve()
    site_path = _linked(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("original reviewed highway site missing")
    map_path = _linked(root, site.get("map_ref"))
    try:
        document = ElementTree.fromstring(map_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise ValueError("reviewed OpenDRIVE map is malformed") from error
    roads = [road for road in document.findall("road")
             if road.get("id") == site.get("road_id")]
    if len(roads) != 1:
        raise ValueError("reviewed highway road absent from OpenDRIVE")
    driving_lanes = {lane.get("id") for lane in roads[0].findall(".//lane")
                     if lane.get("type") == "driving"}
    lanes = site.get("same_direction_lanes")
    if (site.get("highway") is not True or site.get("one_way") is not True or
            not isinstance(lanes, list) or len(lanes) < 2 or
            len({item.get("id") for item in lanes if isinstance(item, dict)}) != len(lanes) or
            any(not isinstance(item, dict) or not item.get("id") or
                item.get("direction") != "travel" or item.get("clearly_marked") is not True
                for item in lanes)):
        raise ValueError("reviewed same-direction marked highway lanes missing")
    if any(item["id"] not in driving_lanes for item in lanes):
        raise ValueError("reviewed lane absent from original OpenDRIVE")
    lane_by_role = site.get("lane_roles", {})
    if (lane_by_role.get("right") != lanes[0]["id"] or
            lane_by_role.get("middle") not in [item["id"] for item in lanes[1:]]):
        raise ValueError("extreme-right and adjacent lane ordering missing")
    cameras = site.get("camera_profiles", {})
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four original camera profiles missing")
    for profile in cameras.values():
        pose = profile.get("pose") if isinstance(profile, dict) else None
        if (not isinstance(profile, dict) or
                not _finite_positive(profile.get("width")) or
                not _finite_positive(profile.get("height")) or
                not isinstance(pose, dict) or
                any(not isinstance(pose.get(key), (int, float)) or
                    isinstance(pose.get(key), bool) or not math.isfinite(pose[key])
                    for key in ("x", "y", "z", "pitch", "yaw", "roll"))):
            raise ValueError("reviewed camera dimensions or pose missing")
    controls = site.get("construction_controls", {})
    required = ("ego_speed_mps", "follower_speed_mps", "slower_speed_mps",
                "ego_start_station_m", "follower_start_station_m", "slower_start_station_m")
    if any(not isinstance(controls.get(key), (int, float)) or isinstance(controls.get(key), bool)
           or not math.isfinite(controls[key]) for key in required):
        raise ValueError("source-reviewed construction controls missing")
    if (not all(_finite_positive(controls[key]) for key in required[:3]) or
            controls["follower_start_station_m"] >= controls["ego_start_station_m"] or
            controls["slower_start_station_m"] <= controls["ego_start_station_m"]):
        raise ValueError("source-reviewed actor ordering or speeds infeasible")
    lane_role, follower, passing = VARIANTS[suffix]
    ego_lane = lane_by_role[lane_role]
    actors = [{"role": "ego", "lane_id": ego_lane,
               "station_m": controls["ego_start_station_m"],
               "target_speed_mps": controls["ego_speed_mps"]}]
    follower_lane = ego_lane if follower else lane_by_role["right"]
    actors.append({"role": "following_vehicle", "lane_id": follower_lane,
                   "station_m": controls["follower_start_station_m"],
                   "target_speed_mps": controls["follower_speed_mps"]})
    if passing:
        actors.append({"role": "slower_vehicle", "lane_id": lane_by_role["right"],
                       "station_m": controls["slower_start_station_m"],
                       "target_speed_mps": controls["slower_speed_mps"]})
    return {"format": "c147344-reviewed-scene-plan-v1", "case_id": case_id,
            "site_sha256": site_ref["sha256"],
            "map_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
            "map_path": str(map_path), "rightmost_lane_id": lane_by_role["right"],
            "requested_immediate_follower": follower,
            "actors": actors, "cameras": cameras, "hz": 20, "frames": 900,
            "physical_acceptance": False, "legal_verdict": None}


def execute_native(scene: dict, adapter: object) -> dict:
    """Call a local adapter; do not import or connect to CARLA at module load."""
    if scene.get("format") != "c147344-reviewed-scene-plan-v1":
        raise ValueError("reviewed scene plan required")
    adapter.open_map(scene["map_path"], scene["map_sha256"])
    actors = {}
    for spec in scene["actors"]:
        actors[spec["role"]] = adapter.spawn_vehicle(**spec)
    cameras = {name: adapter.attach_camera(name=name, ego=actors["ego"],
                                           profile=profile)
               for name, profile in scene["cameras"].items()}
    for frame in range(scene["frames"]):
        adapter.tick_and_capture(frame=frame, hz=scene["hz"], actors=actors, cameras=cameras)
    return {"case_id": scene["case_id"], "actors": actors, "cameras": cameras,
            "frames_requested": scene["frames"], "physical_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output.is_relative_to(args.authority_root.resolve()) or output.exists():
        raise ValueError("fresh scene output must be outside reviewed source root")
    site_ref = json.loads(args.site_ref.read_text(encoding="utf-8"))
    plans = [plan(args.authority_root, site_ref, ASSIGNMENT + "__" + suffix)
             for suffix in VARIANTS]
    output.mkdir(parents=True)
    for suffix, scene in zip(VARIANTS, plans):
        (output / (suffix + ".json")).write_text(
            json.dumps(scene, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_ids": [item["case_id"] for item in plans],
                      "source_sha256": site_ref["sha256"],
                      "physical_acceptance": False}))


if __name__ == "__main__":
    main()
