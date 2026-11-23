"""Source-gated pedestrian route construction for C111329.

This module has no CARLA import at load time. The site packet must be measured
from the local map and device inspection before a Native actor is spawned.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("two-dimensional measured point required")
    p = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in p):
        raise ValueError("nonfinite point")
    return p


def crossing_plan(site: dict, route_kind: str, authorization: bool) -> dict:
    """Build a complete curb-to-curb waypoint route using measured corners.

    site has four clockwise corner coordinates, map provenance, an intersection
    polygon and device inventory. A device's road-facing signal is insufficient.
    """
    if route_kind not in {"adjacent", "opposite"}:
        raise ValueError("unknown route kind")
    for key in ("map_name", "map_sha256", "survey_source", "intersection_polygon", "corners", "devices"):
        if not site.get(key):
            raise ValueError(f"missing site source: {key}")
    corners = [point(p) for p in site["corners"]]
    polygon = [point(p) for p in site["intersection_polygon"]]
    if len(corners) != 4 or len(polygon) < 4 or len(set(corners)) != 4:
        raise ValueError("four distinct corners and intersection polygon required")
    if route_kind == "adjacent":
        start, end = corners[0], corners[1]
    else:
        start, end = corners[0], corners[2]
    if math.dist(start, end) < 2:
        raise ValueError("crossing path too short")
    if authorization:
        supported = [d for d in site["devices"] if d.get("official_source") and d.get("pedestrian_governance") == "diagonal" and d.get("state") == "permissive" and d.get("instruction_source")]
        if not supported:
            raise ValueError("no source-backed official diagonal pedestrian authorization")
    else:
        supported = []
    path = [tuple(start[i] + (end[i] - start[i]) * t / 20 for i in range(2)) for t in range(21)]
    return {"map_name": site["map_name"], "map_sha256": site["map_sha256"], "survey_source": site["survey_source"], "route_kind": route_kind, "start": start, "end": end, "waypoints": path, "intersection_polygon": polygon, "device_inventory_sha256": digest(site["devices"]), "authorizing_device_ids": [d["id"] for d in supported], "exception_484B_290": "unresolved"}


def construct_walker(world, site: dict, route_kind: str, authorization: bool, blueprint_id: str):
    """Spawn a walker at measured corner and command the complete route.

    The adapter supplies location and route-driving methods to avoid a CARLA
    dependency during CPU tests. Actual path execution needs Native readback.
    """
    plan = crossing_plan(site, route_kind, authorization)
    if not blueprint_id.startswith("walker.pedestrian."):
        raise ValueError("walker blueprint required")
    walker = world.spawn_walker(blueprint_id, plan["start"])
    if walker is None:
        raise ValueError("walker spawn failed")
    try:
        world.drive_walker_route(walker, plan["waypoints"])
        if world.walker_id(walker) is None:
            raise ValueError("walker identity readback failed")
        return walker, plan
    except Exception:
        world.destroy_actor(walker)
        raise
