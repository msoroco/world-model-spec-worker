"""Lazy, source-gated Native setup for an NRS 484B.557 stop-distance case.

This module accepts a reviewed crossing site packet. It never infers authority
from a CARLA stop-sign shape or substitutes a nearby intersection sign.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEET_PER_METRE = 3.280839895013123


def _read_source(root: Path, binding: dict, label: str) -> bytes:
    if not isinstance(binding, dict):
        raise ValueError(f"missing {label} binding")
    relative = Path(binding.get("path", ""))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe {label} path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"unsafe {label} path")
    if not path.is_file():
        raise ValueError(f"missing {label} file")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != binding.get("sha256"):
        raise ValueError(f"{label} hash differs")
    return data


def inspect_site(packet_path: Path, case: dict) -> dict:
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("format") != "nrs-484b-557-reviewed-site-v1":
        raise ValueError("reviewed crossing packet required")
    if packet.get("case_id") != case.get("case_id"):
        raise ValueError("site packet selects another exact case")
    sources = packet.get("sources", {})
    opendrive = _read_source(packet_path.parent, sources.get("opendrive"), "opendrive")
    authority = json.loads(_read_source(packet_path.parent, sources.get("crossing_authority"), "crossing authority"))
    geometry = json.loads(_read_source(packet_path.parent, sources.get("crossing_geometry"), "crossing geometry"))
    if authority.get("designation_authority") not in {"state_dot", "local_with_dot_approval"}:
        raise ValueError("designation authority unestablished")
    if authority.get("designation_authority") == "local_with_dot_approval" and not authority.get("dot_approval_source"):
        raise ValueError("local authority lacks DOT approval")
    if authority.get("crossing_type") != "highway_railroad_grade":
        raise ValueError("highway grade crossing unestablished")
    if authority.get("device_type") != "official_stop_sign" or authority.get("device_governs") != "railroad_approach":
        raise ValueError("official stop sign governance unestablished")
    if authority.get("sign_landmark_id") != packet.get("sign_landmark_id"):
        raise ValueError("sign identity differs from authority source")
    if geometry.get("rail_id") != packet.get("rail_id"):
        raise ValueError("rail identity differs from geometry source")
    rail_xy = geometry.get("nearest_rail_xy_m")
    normal = geometry.get("approach_unit_normal_xy")
    if not isinstance(rail_xy, list) or len(rail_xy) != 2 or not isinstance(normal, list) or len(normal) != 2:
        raise ValueError("rail point and approach normal required")
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in rail_xy + normal):
        raise ValueError("nonfinite rail or approach geometry")
    if abs(math.hypot(*normal) - 1.0) > 1e-6:
        raise ValueError("approach normal must be unit length")
    rails = geometry.get("nearest_track_rails")
    if not isinstance(rails, list) or not rails:
        raise ValueError("reviewed nearest-track rail lines required")
    for rail in rails:
        if not isinstance(rail, dict) or not all(key in rail for key in ("a", "b")):
            raise ValueError("reviewed rail line lacks endpoints")
        a, b = rail["a"], rail["b"]
        if (not isinstance(a, list) or not isinstance(b, list) or len(a) != 2 or
                len(b) != 2 or any(type(value) not in (float, int) or
                not math.isfinite(value) for value in a + b) or a == b):
            raise ValueError("reviewed rail line endpoints invalid")
    conflict = None
    if case.get("departure_context") == "crossing_conflict":
        conflict = json.loads(_read_source(packet_path.parent,
                                           sources.get("crossing_conflict"),
                                           "crossing conflict"))
        if (conflict.get("case_id") != case["case_id"] or
                not isinstance(conflict.get("review_citation"), str) or
                not conflict["review_citation"].strip() or
                not str(conflict.get("blueprint_id", "")).startswith("vehicle.")):
            raise ValueError("reviewed crossing-conflict actor source incomplete")
        xyz = conflict.get("spawn_xyz_m")
        if (not isinstance(xyz, list) or len(xyz) != 3 or
                any(type(value) not in (float, int) or not math.isfinite(value)
                    for value in xyz) or
                type(conflict.get("yaw_deg")) not in (float, int) or
                not math.isfinite(conflict["yaw_deg"])):
            raise ValueError("reviewed crossing-conflict pose invalid")
        throttle = conflict.get("throttle")
        if type(throttle) not in (float, int) or not 0 < throttle <= 1:
            raise ValueError("reviewed crossing-conflict motion request invalid")
    if type(case.get("planned_stop_body_gap_ft")) not in (float, int) or case["planned_stop_body_gap_ft"] <= 0:
        raise ValueError("positive planned stop body gap required")
    packet["_opendrive_sha256"] = hashlib.sha256(opendrive).hexdigest()
    packet["_rail_xy"] = rail_xy
    packet["_normal"] = normal
    packet["_authority"] = authority
    packet["_conflict"] = conflict
    packet["_site_dir"] = str(packet_path.parent.resolve())
    return packet


def verify_production_site(packet_path: Path, case: dict) -> dict:
    """Require independently cited original authority and survey sources.

    Source-shaped CPU packets can test geometry, but cannot authorize a GPU run.
    """
    packet = inspect_site(packet_path, case)
    review = packet.get("source_review")
    if not isinstance(review, dict) or review.get("kind") != "original_site_review":
        raise ValueError("independent original crossing site review missing")
    for field in ("reviewer", "review_date", "map_source", "designation_record_citation",
                  "sign_governance_citation", "rail_survey_citation", "camera_pose_citation"):
        value = review.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"original crossing site review lacks {field}")
        if any(word in value.lower() for word in ("synthetic", "fixture", "diagnostic", "placeholder")):
            raise ValueError(f"diagnostic source cannot support {field}")
    authority = packet["_authority"]
    if authority.get("designation_record_citation") != review["designation_record_citation"]:
        raise ValueError("designation citation differs from reviewed authority")
    if authority.get("sign_governance_citation") != review["sign_governance_citation"]:
        raise ValueError("sign governance citation differs from reviewed authority")
    if packet["_conflict"] is not None:
        citation = review.get("crossing_conflict_citation")
        if (not isinstance(citation, str) or not citation.strip() or
                packet["_conflict"]["review_citation"] != citation or
                any(word in citation.lower() for word in
                    ("synthetic", "fixture", "diagnostic", "placeholder"))):
            raise ValueError("original crossing-conflict actor review missing")
    from native_camera import validate_plan
    cameras = validate_plan(packet_path)
    if any(item["pose_source_citation"] != review["camera_pose_citation"] for item in cameras):
        raise ValueError("camera poses differ from reviewed original source")
    return packet


def planned_ego_center_xy(packet: dict, case: dict) -> tuple[float, float]:
    """Offset the vehicle centre from a rail by body length plus target gap.

    This is a construction target only. Original sampled body geometry decides
    the measured stop distance.
    """
    extent = packet.get("ego_longitudinal_half_extent_m")
    if type(extent) not in (float, int) or not math.isfinite(extent) or extent <= 0:
        raise ValueError("source-reviewed ego half extent required")
    gap = case["planned_stop_body_gap_ft"] / FEET_PER_METRE
    rail = packet["_rail_xy"]
    nx, ny = packet["_normal"]
    return rail[0] - nx * (extent + gap), rail[1] - ny * (extent + gap)


def create(world, packet_path: Path, case: dict, transform_factory):
    """Verify live map/sign, spawn ego at a reviewed crossing approach."""
    packet = verify_production_site(packet_path, case)
    live_map = world.get_map()
    if hashlib.sha256(live_map.to_opendrive().encode()).hexdigest() != packet["_opendrive_sha256"]:
        raise ValueError("live OpenDRIVE differs from reviewed source")
    landmarks = {str(item.id) for item in live_map.get_all_landmarks()}
    if str(packet["sign_landmark_id"]) not in landmarks:
        raise ValueError("reviewed crossing stop sign absent from Native map")
    x, y = planned_ego_center_xy(packet, case)
    approach_distance = packet.get("approach_distance_m")
    if type(approach_distance) not in (float, int) or not math.isfinite(approach_distance) or approach_distance <= 0:
        raise ValueError("positive reviewed upstream approach distance required")
    nx, ny = packet["_normal"]
    spawn_x, spawn_y = x - nx * approach_distance, y - ny * approach_distance
    blueprint_id = packet.get("ego_blueprint_id")
    if not isinstance(blueprint_id, str) or not blueprint_id.startswith("vehicle."):
        raise ValueError("reviewed motor-vehicle blueprint required")
    blueprint = world.get_blueprint_library().find(blueprint_id)
    transform = transform_factory(spawn_x, spawn_y, packet["_normal"])
    ego = world.try_spawn_actor(blueprint, transform)
    if ego is None:
        raise ValueError("Native ego spawn failed")
    conflict_actor = None
    try:
        if packet["_conflict"] is not None:
            reviewed = packet["_conflict"]
            conflict_blueprint = world.get_blueprint_library().find(reviewed["blueprint_id"])
            pose = transform_factory(reviewed["spawn_xyz_m"][0],
                                     reviewed["spawn_xyz_m"][1],
                                     [math.cos(math.radians(reviewed["yaw_deg"])),
                                      math.sin(math.radians(reviewed["yaw_deg"]))],
                                     reviewed["spawn_xyz_m"][2])
            conflict_actor = world.try_spawn_actor(conflict_blueprint, pose)
            if conflict_actor is None:
                raise ValueError("Native crossing-conflict actor spawn failed")
    except BaseException:
        ego.destroy()
        raise
    return {"ego": ego, "conflict_actor": conflict_actor, "packet": packet, "planned_center_xy_m": [x, y],
            "spawn_center_xy_m": [spawn_x, spawn_y],
            "planned_gap_ft": case["planned_stop_body_gap_ft"]}
