"""Source-gated trail-to-street bicycle construction for LVMC 11.22.120(B)."""
from __future__ import annotations

import hashlib
import json
import math


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _point(value):
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
        raise ValueError("source point must have three finite coordinates")
    return value


def validate_site(site: dict) -> dict:
    """Require external designation, governed roadway, actual sign and connected route."""
    for key in ("map_name", "jurisdiction_source", "engineer_designation_source", "street_id", "bicycle_blueprint_id"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError(f"missing original site field: {key}")
    if site.get("designation_street_id") != site["street_id"]:
        raise ValueError("designation does not bind governed street")
    if site.get("designation_prohibits_bicycle_roadway_use") is not True:
        raise ValueError("designation lacks bicycle roadway restriction")
    segments = site.get("route_segments")
    if not isinstance(segments, list) or len(segments) < 2:
        raise ValueError("trail and street route segments required")
    if segments[0].get("kind") != "nonmotorized_trail" or segments[1].get("kind") != "governed_street_roadway":
        raise ValueError("route must connect trail to governed street roadway")
    if segments[1].get("street_id") != site["street_id"]:
        raise ValueError("route street differs from designation")
    for segment in segments[:2]:
        start, end = _point(segment.get("start")), _point(segment.get("end"))
        if math.dist(start, end) < 1.0:
            raise ValueError("degenerate route segment")
    if math.dist(segments[0]["end"], segments[1]["start"]) > 0.5:
        raise ValueError("trail route does not connect to street")
    sign = site.get("sign")
    if not isinstance(sign, dict) or sign.get("street_id") != site["street_id"]:
        raise ValueError("sign does not govern designated street")
    for key in ("source_id", "wording", "facing_direction", "erection_source"):
        if not isinstance(sign.get(key), str) or not sign[key].strip():
            raise ValueError(f"missing original sign field: {key}")
    _point(sign.get("position"))
    if sign.get("posted") is not True or sign.get("prohibits_bicycle_roadway_use") is not True:
        raise ValueError("posted sign does not state bicycle roadway restriction")
    return {"site_sha256": canonical_sha(site), "street_id": site["street_id"], "sign_source_id": sign["source_id"]}


def spawn_bicycle(world, transform, site: dict):
    """Call Native spawn/readback only after site source validation."""
    validate_site(site)
    blueprint = world.get_blueprint_library().find(site["bicycle_blueprint_id"])
    bike = world.try_spawn_actor(blueprint, transform)
    if bike is None or not bike.is_alive or bike.type_id != site["bicycle_blueprint_id"]:
        raise ValueError("Native bicycle spawn/readback failed")
    return bike


def command_bicycle(bike, carla, site: dict, case: dict, elapsed_s: float) -> dict:
    validate_site(site)
    if not bike.is_alive or bike.type_id != site["bicycle_blueprint_id"]:
        raise ValueError("Native bicycle readback failed")
    if case.get("motion") not in ("enter_roadway", "remain_trail", "stop_before_roadway"):
        raise ValueError("unknown case motion")
    segment = site["route_segments"][0 if case["motion"] == "remain_trail" else 1]
    start, end = segment["start"], segment["end"]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1.0:
        raise ValueError("degenerate route segment")
    speed = 0.0 if case["motion"] == "stop_before_roadway" and elapsed_s >= 3.0 else float(site.get("engineering_speed_mps", 3.0))
    if not math.isfinite(speed) or not 0 <= speed <= 8:
        raise ValueError("unsafe engineering speed")
    command = carla.Vector3D(x=dx / length * speed, y=dy / length * speed, z=0.0)
    bike.set_target_velocity(command)
    actual = bike.get_velocity()
    if not all(math.isfinite(v) for v in (actual.x, actual.y, actual.z)):
        raise ValueError("Native velocity readback unavailable")
    return {"source_kind": "original_native_control_readback", "actor_id": str(bike.id), "site_sha256": canonical_sha(site), "elapsed_s": elapsed_s, "motion": case["motion"], "observed_velocity_mps": [actual.x, actual.y, actual.z]}
