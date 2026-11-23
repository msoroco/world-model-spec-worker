"""Lazy, source-gated construction for the assigned U-turn prohibition cell."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


class ConstructionError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise ConstructionError(reason)


def load_site(path: Path, sha256: str, case_id: str) -> dict:
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha256, "site source hash mismatch")
    site = json.loads(raw)
    require(site.get("case_id") == case_id, "case mismatch")
    require(site.get("map_name") and site.get("map_sha256"), "map source missing")
    require(site.get("highway_status", {}).get("source_sha256"), "highway source missing")
    device = site.get("device", {})
    require(device.get("authority_source_sha256") and device.get("legal_consistency_source_sha256"), "official device source missing")
    require(device.get("display_source_sha256") and device.get("governed_approach"), "display source missing")
    require(device.get("prohibits_u_turn") is not None, "display meaning missing")
    require(device.get("position_xy_m") and len(device["position_xy_m"]) == 2, "device position missing")
    route = site.get("u_turn_route", [])
    require(len(route) >= 3, "reviewed U-turn route missing")
    require(route[0].get("road_id") == route[-1].get("road_id"), "U-turn road mismatch")
    require(route[0].get("lane_id") != route[-1].get("lane_id"), "opposite destination lane missing")
    require(site.get("ego_blueprint", "").startswith("vehicle."), "motor vehicle blueprint missing")
    require(site.get("ego_spawn") is not None, "ego spawn missing")
    require(site.get("device_blueprint"), "device construction missing")
    return site


def construct(world, site: dict, *, ego_transform, device_transform):
    """Spawn reviewed vehicle/device; caller owns cleanup and world restoration."""
    require(world.get_map().name == site["map_name"], "wrong live map")
    library = world.get_blueprint_library()
    ego = world.try_spawn_actor(library.find(site["ego_blueprint"]), ego_transform)
    require(ego is not None, "ego spawn failed")
    try:
        device = world.try_spawn_actor(library.find(site["device_blueprint"]), device_transform)
        require(device is not None, "device spawn failed")
    except Exception:
        ego.destroy()
        raise
    return {"ego": ego, "device": device, "route": site["u_turn_route"], "governed_approach": site["device"]["governed_approach"]}
