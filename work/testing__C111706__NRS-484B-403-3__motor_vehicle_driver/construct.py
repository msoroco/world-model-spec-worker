"""Lazy CARLA construction for the assigned intersection U-turn cell.

The caller supplies a source-reviewed site and transforms from original map
survey. No actor is moved by teleportation after construction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ConstructionError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise ConstructionError(message)


def load_site(path: Path, expected_sha256: str, *, expected_case: str) -> dict:
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "site source hash mismatch")
    site = json.loads(raw)
    _require(site.get("case_id") == expected_case, "case identity mismatch")
    _require(site.get("map_sha256") and site.get("district_source_sha256"), "map or district source missing")
    _require(site.get("intersection_boundary_source_sha256"), "intersection boundary source missing")
    route = site.get("ego_route", [])
    _require(len(route) >= 3, "U-turn route too short")
    _require(route[0]["road_id"] == route[-1]["road_id"], "U-turn road mismatch")
    _require(route[0]["lane_id"] != route[-1]["lane_id"], "opposite lane missing")
    in_junction = any(p.get("junction_id") is not None for p in route)
    outside_case = expected_case.endswith("__approach_before_intersection")
    _require(in_junction != outside_case, "route intersection occupancy mismatches case")
    _require(site.get("ego_blueprint", "").startswith("vehicle."), "ego blueprint missing")
    _require(site.get("other_blueprint", "").startswith("vehicle."), "other vehicle blueprint missing")
    _require(site.get("other_route") and site.get("other_spawn"), "other vehicle route/spawn missing")
    return site


def construct(world, site: dict, *, ego_spawn, other_spawn):
    """Spawn both actors; return owned actors and reviewed route definitions.

    CARLA setup ownership stays with the caller, which must destroy both actors
    and restore world settings in a guaranteed cleanup block.
    """
    map_name = world.get_map().name
    _require(map_name == site["map_name"], "wrong live map")
    library = world.get_blueprint_library()
    ego_bp = library.find(site["ego_blueprint"])
    other_bp = library.find(site["other_blueprint"])
    ego = world.try_spawn_actor(ego_bp, ego_spawn)
    _require(ego is not None, "ego spawn failed")
    try:
        other = world.try_spawn_actor(other_bp, other_spawn)
        _require(other is not None, "other vehicle spawn failed")
    except Exception:
        ego.destroy()
        raise
    return {"ego": ego, "other_vehicle": other,
            "ego_route": site["ego_route"], "other_route": site["other_route"]}
