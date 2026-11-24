"""Spawn one planned reversal case from an immutable reviewed Native site.

This is a portable CARLA-facing constructor. It needs a reviewed OpenDRIVE map,
route stations, blueprint IDs and exact spawn transforms. It does not invent
those source facts or start the reversal controller/cameras.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from carla_sight_adapter import load_reviewed_site
from sight_measurement import ASSIGNMENT


DISTANCE_TARGETS_FT = {
    "distance_reference": 500,
    "distance_below_500ft": 499,
    "distance_at_500ft": 500,
    "distance_above_500ft": 501,
}


def _spawn_transform(row: dict, transform_factory):
    xyz = row.get("location")
    yaw = row.get("yaw_deg")
    if (not isinstance(xyz, dict) or
            any(type(xyz.get(axis)) not in (int, float) or
                not math.isfinite(xyz[axis]) for axis in ("x", "y", "z")) or
            type(yaw) not in (int, float) or not math.isfinite(yaw) or
            type(row.get("road_id")) is not int or
            type(row.get("lane_id")) is not int):
        raise ValueError("reviewed spawn transform and road lane required")
    return transform_factory(xyz["x"], xyz["y"], xyz["z"], yaw)


def construct_case(world, blueprint_library, site_path: Path,
                   site_sha256: str, case_id: str, transform_factory):
    """Return two live actors; caller owns their eventual destruction."""
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in DISTANCE_TARGETS_FT:
        raise ValueError("unsupported exact reversal case")
    site = load_reviewed_site(site_path, site_sha256)
    loaded_digest = hashlib.sha256(world.get_map().to_opendrive().encode("utf-8")).hexdigest()
    if loaded_digest != site.get("map_source_sha256"):
        raise ValueError("loaded map differs from reviewed case site")
    settings = world.get_settings()
    if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - 0.05) > 1e-8:
        raise ValueError("Native construction requires synchronous 20 Hz world")
    setup = site.get("case_setups", {}).get(case_id)
    if not isinstance(setup, dict) or setup.get("target_first_turn_distance_ft") != DISTANCE_TARGETS_FT[suffix]:
        raise ValueError("reviewed exact distance case setup missing")
    actor_rows = [setup.get("ego_spawn"), setup.get("approach_spawn")]
    if any(not isinstance(row, dict) for row in actor_rows):
        raise ValueError("both reviewed actor spawns required")
    world_map = world.get_map()
    transforms = []
    for row in actor_rows:
        transform = _spawn_transform(row, transform_factory)
        waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
        if (waypoint is None or waypoint.road_id != row["road_id"] or
                waypoint.lane_id != row["lane_id"]):
            raise ValueError("actor spawn differs from reviewed road lane")
        transforms.append(transform)
    blueprint_ids = [site.get("ego_blueprint_id"), site.get("approach_blueprint_id")]
    if any(not isinstance(bp, str) or not bp.startswith("vehicle.") for bp in blueprint_ids):
        raise ValueError("reviewed vehicle blueprints required")
    blueprints = [blueprint_library.find(bp) for bp in blueprint_ids]
    actors = []
    try:
        for blueprint, transform, expected_type in zip(blueprints, transforms, blueprint_ids):
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("reviewed actor spawn failed")
            actors.append(actor)
            if actor.type_id != expected_type:
                raise ValueError("spawned actor blueprint differs from reviewed site")
        if actors[0].id == actors[1].id:
            raise ValueError("subject and approach actor identities collided")
        return tuple(actors)
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise
