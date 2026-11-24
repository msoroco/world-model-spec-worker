"""Source-gated diagonal pedestrian construction and original-frame readback.

The packet is a measured site proposal. Its authority records must be checked
against original documents; a CARLA traffic light alone cannot authorize a
pedestrian diagonal crossing. No legal outcome is inferred here.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("measured map-XY point required")
    point = tuple(float(n) for n in value)
    if not all(math.isfinite(n) for n in point):
        raise ValueError("nonfinite point")
    return point


def _source(packet, name, root=None):
    item = packet.get("sources", {}).get(name)
    if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
        raise ValueError(f"missing source: {name}")
    file = Path(item["path"])
    if root is not None:
        base = Path(root).resolve()
        original = base / file
        file = original.resolve()
        if not file.is_relative_to(base) or original.is_symlink():
            raise ValueError(f"source escapes attempt: {name}")
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"source hash mismatch: {name}")
    return item


def validate_site(packet, root=None):
    for name in ("map", "corner_survey", "authorization", "device_inventory", "exception_review"):
        _source(packet, name, root)
    if packet.get("coordinate_frame") != "map_xy_m":
        raise ValueError("unsupported coordinate frame")
    corners = [_point(p) for p in packet["corners_clockwise"]]
    if len(corners) != 4 or len(set(corners)) != 4:
        raise ValueError("four surveyed, distinct intersection corners required")
    start, destination = corners[0], corners[2]
    if math.dist(start, destination) < 3:
        raise ValueError("diagonal endpoints too close")
    route = [_point(p) for p in packet["pedestrian_route"]]
    if len(route) < 3 or math.dist(route[0], start) > 0.5 or math.dist(route[-1], destination) > 0.5:
        raise ValueError("route must connect opposite surveyed corners")
    if not all(math.dist(a, b) > 0.1 for a, b in zip(route, route[1:])):
        raise ValueError("zero-length route segment")
    device = packet["governing_device"]
    for name in ("id", "authority_record_id", "instruction_record_id", "placement_record_id"):
        if not device.get(name):
            raise ValueError(f"missing governing device provenance: {name}")
    if device.get("governs") != "pedestrian_diagonal" or device.get("diagonal_authorized") is not True:
        raise ValueError("official pedestrian diagonal authorization unestablished")
    if device["id"] not in packet.get("observed_device_ids", []):
        raise ValueError("governing device not inventoried on site")
    if packet.get("exception_484b_290_review") not in {"not_applicable_source_review", "unresolved"}:
        raise ValueError("exception review missing")
    return {"start_xy": start, "destination_xy": destination,
            "route_xy": route, "device_id": device["id"],
            "source_sha256": {name: packet["sources"][name]["sha256"] for name in
                              ("map", "corner_survey", "authorization", "device_inventory", "exception_review")},
            "exception_484b_290_review": packet["exception_484b_290_review"]}


def spawn_walker(world, packet, *, carla_module=None):
    plan = validate_site(packet)
    blueprint_id = packet.get("walker_blueprint_id")
    if not isinstance(blueprint_id, str) or not blueprint_id.startswith("walker.pedestrian."):
        raise ValueError("walker blueprint ID required")
    if carla_module is None:
        import carla as carla_module
    start = plan["start_xy"]
    transform = carla_module.Transform(carla_module.Location(x=start[0], y=start[1], z=float(packet["spawn_z_m"])))
    blueprint = world.get_blueprint_library().find(blueprint_id)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise RuntimeError("walker spawn failed")
    try:
        if actor.type_id != blueprint_id:
            raise ValueError("walker blueprint readback mismatch")
        location = actor.get_location()
        if math.hypot(location.x - start[0], location.y - start[1]) > 1.0:
            raise ValueError("walker start readback mismatch")
        return actor, plan
    except Exception:
        actor.destroy()
        raise


def advance_walker(actor, plan, route_index, speed_mps, *, carla_module=None):
    if carla_module is None:
        import carla as carla_module
    if not 1 <= route_index < len(plan["route_xy"]):
        raise ValueError("route index out of range")
    if not math.isfinite(float(speed_mps)) or float(speed_mps) <= 0:
        raise ValueError("positive speed required")
    target = plan["route_xy"][route_index]
    location = actor.get_location()
    distance = math.hypot(target[0] - location.x, target[1] - location.y)
    if distance < 0.35 and route_index + 1 < len(plan["route_xy"]):
        route_index += 1
        target = plan["route_xy"][route_index]
        distance = math.hypot(target[0] - location.x, target[1] - location.y)
    if distance < 0.35:
        actor.apply_control(carla_module.WalkerControl(direction=carla_module.Vector3D(0, 0, 0), speed=0))
        return route_index
    direction = carla_module.Vector3D((target[0] - location.x) / distance, (target[1] - location.y) / distance, 0)
    actor.apply_control(carla_module.WalkerControl(direction=direction, speed=float(speed_mps)))
    return route_index
