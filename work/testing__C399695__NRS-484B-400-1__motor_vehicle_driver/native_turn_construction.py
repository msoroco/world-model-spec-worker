"""Review-gated Native request for distinct approach and turning lane positions."""

import hashlib
import json
import math
from pathlib import Path

from turn_position import validate_site


AID = "testing__C399695__NRS-484B-400-1__motor_vehicle_driver"
VARIANTS = {
    "lane_both_intervals": (True, "turn", "turn"),
    "approach_from_other_lane": (True, "extreme", "turn"),
    "turn_from_other_lane": (True, "turn", "extreme"),
    "other_lane_both_intervals": (True, "extreme", "extreme"),
    "extreme_right_no_qualifying_lane": (False, "extreme", "extreme"),
}


def source_packet(path, case_id):
    """Load a sealed original site packet; never invent a map or lane geometry."""
    path = Path(path).resolve()
    packet = json.loads(path.read_text())
    if packet.get("assignment_id") != AID or packet.get("case_id") != case_id:
        raise ValueError("exact assignment/case source packet required")
    if packet.get("source_kind") != "original_native_map_geometry" or packet.get("reviewed_original_native_site") is not True:
        raise ValueError("reviewed original Native site required")
    refs = packet.get("source_refs")
    roles = {"map", "public_highway", "non_alley_intersection", "lane_design",
             "qualification_223_4", "connected_right_exit", "driver_identity",
             "intended_right_turn", "vehicle_spawn", "approach_trajectory",
             "turn_trajectory", "turn_lane_connectors"}
    if not isinstance(refs, list) or roles - {item.get("role") for item in refs}:
        raise ValueError("independent original site sources missing")
    for item in refs:
        target = (path.parent / item["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or target.is_symlink():
            raise ValueError("missing reviewed site source: " + str(item.get("role")))
        if hashlib.sha256(target.read_bytes()).hexdigest() != item.get("sha256"):
            raise ValueError("reviewed site source hash differs: " + str(item.get("role")))
    if packet["map_sha256"] != next(item["sha256"] for item in refs if item["role"] == "map"):
        raise ValueError("Native map hash differs")
    return packet


def construct(site, case_id):
    suffix = case_id.removeprefix(AID + "__")
    if not case_id.startswith(AID + "__") or suffix not in VARIANTS:
        raise ValueError("unsupported exact NRS 484B.400(1) case")
    validate_site(site)
    qualified, approach_key, turn_key = VARIANTS[suffix]
    if site["right_turn_lane_qualified_under_223_4"] is not qualified:
        raise ValueError("reviewed conditional lane qualification differs")
    intention = site.get("intended_maneuver")
    if not isinstance(intention, dict) or intention.get("maneuver") != "right_turn" or not intention.get("source_ref"):
        raise ValueError("independent right-turn intention source required")
    spawn = site.get("native_spawn")
    if not isinstance(spawn, dict) or not spawn.get("source_id") or not spawn.get("blueprint_id") or not isinstance(spawn.get("pose_xyz_ypr"), list) or len(spawn["pose_xyz_ypr"]) != 6:
        raise ValueError("source-surveyed Native vehicle spawn required")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in spawn["pose_xyz_ypr"]):
        raise ValueError("finite Native vehicle pose required")
    paths = site.get("trajectories")
    if not isinstance(paths, dict):
        raise ValueError("source-surveyed approach and turn trajectories required")
    for key in ("turn", "extreme"):
        item = paths.get(key)
        if not isinstance(item, dict) or not item.get("source_ref") or not isinstance(item.get("xy"), list) or len(item["xy"]) < 3:
            raise ValueError("source-surveyed trajectory missing: " + key)
        for point in item["xy"]:
            if not isinstance(point, list) or len(point) != 2 or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in point):
                raise ValueError("finite world trajectory point required")
    if not site.get("source_confirmed_lane_change_feasible") and approach_key != turn_key:
        raise ValueError("source-confirmed approach-to-turn lane change required")
    return {"case_id": case_id, "conditional_lane_qualification": qualified,
            "approach_lane_id": site["turn_lane_id"] if approach_key == "turn" else site["extreme_right_lane_id"],
            "turn_lane_id": site["turn_lane_id"] if turn_key == "turn" else site["extreme_right_lane_id"],
            "approach_trajectory_xy": paths[approach_key]["xy"],
            "turn_trajectory_xy": paths[turn_key]["xy"],
            "turn_phase_lane_refs": site["turn_phase_lane_refs"][turn_key],
            "trajectory_sources": [paths[approach_key]["source_ref"], paths[turn_key]["source_ref"]],
            "intention_source": intention["source_ref"],
            "native_map_sha256": site["map_sha256"], "driver_id": site["driver_id"],
            "original_20hz_readback_required": True}
