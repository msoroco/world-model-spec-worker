"""Source-gated bicycle and rack spawn with Native readback and cleanup."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_geometry import RACK_ENVELOPE_XY_M


def read_asset_inventory(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Native blueprint inventory hash mismatch")
    inventory = json.loads(raw)
    if inventory.get("source_kind") != "original_local_native_blueprint_inventory" or not inventory.get("world_map"):
        raise ValueError("Native blueprint inventory source unverified")
    if not isinstance(inventory.get("blueprint_ids"), list):
        raise ValueError("Native blueprint inventory lacks IDs")
    return inventory


def _blueprint(library, blueprint_id):
    try:
        blueprint = library.find(blueprint_id)
    except (KeyError, RuntimeError) as exc:
        raise ValueError("Native blueprint unavailable: " + blueprint_id) from exc
    if blueprint is None or blueprint.id != blueprint_id:
        raise ValueError("Native blueprint unavailable: " + blueprint_id)
    return blueprint


def _vertices_xy(actor):
    body = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(body) != 8:
        raise ValueError("Native actor body readback incomplete")
    return [(float(v.x), float(v.y)) for v in body]


def spawn_bicycle_and_rack(world, carla, scene: dict, inventory: dict):
    """Spawn actual assets, verify body and type, destroy both on any failure."""
    bicycle_id = scene.get("bicycle_blueprint_id")
    rack_id = scene.get("rack_blueprint_id")
    if not bicycle_id or not rack_id or bicycle_id == rack_id:
        raise ValueError("distinct bicycle and rack blueprint IDs required")
    if inventory.get("source_kind") != "original_local_native_blueprint_inventory" or not set((bicycle_id, rack_id)) <= set(inventory.get("blueprint_ids", [])):
        raise ValueError("source-gated bicycle/rack inventory missing assets")
    library = world.get_blueprint_library()
    actors = []
    try:
        bicycle_bp = _blueprint(library, bicycle_id)
        rack_bp = _blueprint(library, rack_id)
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(carla.Location(x=-30., y=-.75, z=.25), carla.Rotation(yaw=0.)))
        if bicycle is None:
            raise RuntimeError("Native bicycle spawn failed")
        actors.append(bicycle)
        rack = world.spawn_actor(rack_bp, carla.Transform(carla.Location(x=0., y=2.3, z=0.), carla.Rotation(yaw=0.)))
        if rack is None:
            raise RuntimeError("Native rack spawn failed")
        actors.append(rack)
        if bicycle.type_id != bicycle_id or rack.type_id != rack_id:
            raise ValueError("Native actor type readback mismatch")
        bicycle_body = _vertices_xy(bicycle)
        rack_body = _vertices_xy(rack)
        if max(abs(y + .75) for _, y in bicycle_body) >= 1.25:
            raise ValueError("Native bicycle body outside alley route")
        x0, y0, x1, y1 = RACK_ENVELOPE_XY_M
        if not all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in rack_body):
            raise ValueError("Native rack body outside reviewed envelope")
        return bicycle, rack, actors
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise
