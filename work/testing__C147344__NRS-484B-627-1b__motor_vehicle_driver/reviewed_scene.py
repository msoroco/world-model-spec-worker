"""Source-gated four-case Native scene plan for NRS 484B.627(1)(b).

The reviewed site packet supplies geometry and feasible speed controls. A plan
is a request for local CARLA construction, never a legal or physical finding.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C147344__NRS-484B-627-1b__motor_vehicle_driver"
VARIANTS = {
    "slow_middle_follower": ("middle", True, False),
    "slow_right_follower": ("right", True, False),
    "slow_middle_passing": ("middle", True, True),
    "slow_middle_no_immediate_follower": ("middle", False, False),
}
CAMERAS = ("overview", "approach", "reference_corner", "conflict")


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
    lanes = site.get("same_direction_lanes")
    if (site.get("highway") is not True or site.get("one_way") is not True or
            not isinstance(lanes, list) or len(lanes) < 2 or
            len({item.get("id") for item in lanes if isinstance(item, dict)}) != len(lanes) or
            any(not isinstance(item, dict) or not item.get("id") or
                item.get("direction") != "travel" or item.get("clearly_marked") is not True
                for item in lanes)):
        raise ValueError("reviewed same-direction marked highway lanes missing")
    lane_by_role = site.get("lane_roles", {})
    if (lane_by_role.get("right") != lanes[0]["id"] or
            lane_by_role.get("middle") not in [item["id"] for item in lanes[1:]]):
        raise ValueError("extreme-right and adjacent lane ordering missing")
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
            "actors": actors, "cameras": list(CAMERAS), "hz": 20, "frames": 900,
            "physical_acceptance": False, "legal_verdict": None}


def execute_native(scene: dict, adapter: object) -> dict:
    """Call a local adapter; do not import or connect to CARLA at module load."""
    if scene.get("format") != "c147344-reviewed-scene-plan-v1":
        raise ValueError("reviewed scene plan required")
    adapter.open_map(scene["map_path"], scene["map_sha256"])
    actors = {}
    for spec in scene["actors"]:
        actors[spec["role"]] = adapter.spawn_vehicle(**spec)
    cameras = {name: adapter.attach_camera(name=name, ego=actors["ego"])
               for name in scene["cameras"]}
    for frame in range(scene["frames"]):
        adapter.tick_and_capture(frame=frame, hz=scene["hz"], actors=actors, cameras=cameras)
    return {"case_id": scene["case_id"], "actors": actors, "cameras": cameras,
            "frames_requested": scene["frames"], "physical_acceptance": False}
