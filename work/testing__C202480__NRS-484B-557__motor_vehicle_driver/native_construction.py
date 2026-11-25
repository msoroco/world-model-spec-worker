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
    if type(case.get("planned_stop_body_gap_ft")) not in (float, int) or case["planned_stop_body_gap_ft"] <= 0:
        raise ValueError("positive planned stop body gap required")
    packet["_opendrive_sha256"] = hashlib.sha256(opendrive).hexdigest()
    packet["_rail_xy"] = rail_xy
    packet["_normal"] = normal
    packet["_authority"] = authority
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
    return {"ego": ego, "packet": packet, "planned_center_xy_m": [x, y],
            "spawn_center_xy_m": [spawn_x, spawn_y],
            "planned_gap_ft": case["planned_stop_body_gap_ft"]}
