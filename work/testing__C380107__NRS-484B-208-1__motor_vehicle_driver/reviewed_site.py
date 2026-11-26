"""SHA-sealed original highway and HOV source gate for Native construction."""

import hashlib
import json
import math
from pathlib import Path

from hov_controls import selected_schedule
from package_contract import ASSIGNMENT, CELL


SOURCES = ("opendrive", "lane_geometry", "posted_limit", "geographical_boundary",
           "hov_designation", "hov_hours", "hov_occupancy_rule", "hov_access",
           "hov_sign", "hov_vehicle_category", "hov_compliance",
           "knowledge_circumstances", "other_exceptions", "actor_poses")


def source(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
        raise ValueError("reviewed original source path and SHA-256 required")
    root = Path(root).resolve()
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("reviewed original source missing or escapes authority root")
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("reviewed original source bytes changed")
    return path


def plan(root, site_ref, case_id):
    site_path = source(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("source_kind") != "reviewed_original_highway_site" or site.get("cell_id") != CELL:
        raise ValueError("reviewed original C380107 controlled-access site required")
    paths = {key: source(root, site.get(key)) for key in SOURCES}
    geometry = json.loads(paths["lane_geometry"].read_text(encoding="utf-8"))
    if geometry.get("controlled_access") is not True or geometry.get("clearly_marked_same_direction") is not True:
        raise ValueError("controlled-access marked same-direction geometry required")
    lanes = geometry.get("same_direction_lane_ids")
    if not isinstance(lanes, list) or len(lanes) < 2 or len(set(map(str, lanes))) != len(lanes):
        raise ValueError("two distinct reviewed same-direction lanes required")
    left, right = geometry.get("extreme_left_lane_id"), geometry.get("right_response_lane_id")
    if left not in lanes or right not in lanes or left == right:
        raise ValueError("reviewed extreme-left and adjacent right lane identities required")
    limit_record = json.loads(paths["posted_limit"].read_text(encoding="utf-8"))
    limit = limit_record.get("posted_limit_mps")
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0:
        raise ValueError("source-backed positive posted limit required")
    poses = json.loads(paths["actor_poses"].read_text(encoding="utf-8"))
    for key in ("ego", "rear"):
        actor = poses.get(key)
        if not isinstance(actor, dict) or not str(actor.get("blueprint_id", "")).startswith("vehicle."):
            raise ValueError("reviewed motor vehicle actor pose/blueprint required: " + key)
        pose = actor.get("spawn_pose")
        if not isinstance(pose, dict) or any(k not in pose or not isinstance(pose[k], (int, float)) or
                                              not math.isfinite(pose[k]) for k in ("x", "y", "z", "yaw")):
            raise ValueError("finite reviewed actor pose required: " + key)
    if set(poses.get("camera_poses", {})) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four reviewed original camera poses required")
    schedule = selected_schedule(case_id, float(limit))
    designation = json.loads(paths["hov_designation"].read_text(encoding="utf-8"))
    if (designation.get("source_kind") != "original_authority" or
            designation.get("state") != schedule["hov_designation_request"]):
        raise ValueError("reviewed HOV designation does not realize selected request")
    for key in ("geographical_boundary", "hov_hours", "hov_occupancy_rule", "hov_access",
                "hov_sign", "hov_vehicle_category", "knowledge_circumstances", "other_exceptions"):
        packet = json.loads(paths[key].read_text(encoding="utf-8"))
        if packet.get("source_kind") != "original_authority":
            raise ValueError("original HOV authority missing: " + key)
    compliance = json.loads(paths["hov_compliance"].read_text(encoding="utf-8"))
    if (compliance.get("source_kind") != "original_authority" or
            compliance.get("state") != schedule["hov_compliance_request"]):
        raise ValueError("reviewed HOV compliance does not realize selected request")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "authority_root": str(Path(root).resolve()), "site_path": str(site_path),
            "site_sha256": site_ref["sha256"], "source_refs": {k: site[k] for k in SOURCES},
            "map_path": str(paths["opendrive"]), "posted_limit_mps": float(limit),
            "same_direction_lane_ids": lanes, "extreme_left_lane_id": left,
            "right_response_lane_id": right, "actor_poses": poses,
            "schedule": schedule, "legal_judgment": "unresolved"}
