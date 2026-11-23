"""Lazy CARLA pedestrian construction for a source-specified crossing route."""

from __future__ import annotations

import math

from site_geometry import assess_site


def spawn_pedestrian(world, packet: dict, *, carla_module=None):
    """Spawn the route actor only after site packets pass source/geometry checks.

    The caller owns cleanup and must retain original transform/actor history.
    No traffic light or stripe is conjured by this function: the site packet
    must be checked against the actual map and authority/survey sources.
    """
    assess_site(packet, require_operating=False)
    blueprint_id = packet.get("walker_blueprint_id")
    if not isinstance(blueprint_id, str) or not blueprint_id.startswith("walker.pedestrian."):
        raise ValueError("source-selected walker blueprint required")
    speed = float(packet.get("walker_speed_mps", 0))
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("positive walker speed required")
    if carla_module is None:
        import carla as carla_module
    start = packet["pedestrian_route"][0]
    spawn_z = float(packet.get("spawn_z_m", 0))
    transform = carla_module.Transform(carla_module.Location(x=float(start[0]), y=float(start[1]), z=spawn_z))
    blueprint = world.get_blueprint_library().find(blueprint_id)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise RuntimeError("walker spawn failed")
    try:
        if actor.type_id != blueprint_id:
            raise ValueError("spawned walker blueprint mismatch")
        location = actor.get_location()
        if math.hypot(location.x - float(start[0]), location.y - float(start[1])) > float(packet.get("spawn_readback_tolerance_m", 1.0)):
            raise ValueError("walker spawn readback outside engineering tolerance")
        return actor
    except Exception:
        actor.destroy()
        raise


def advance_pedestrian(actor, packet: dict, route_index: int, *, carla_module=None) -> int:
    """Apply one deterministic route segment; return next route target index."""
    if carla_module is None:
        import carla as carla_module
    route = packet["pedestrian_route"]
    if not 1 <= route_index < len(route):
        raise ValueError("route target index out of bounds")
    target = route[route_index]
    location = actor.get_location()
    delta_x, delta_y = float(target[0]) - location.x, float(target[1]) - location.y
    distance = math.hypot(delta_x, delta_y)
    if distance <= float(packet.get("waypoint_tolerance_m", 0.35)):
        if route_index == len(route) - 1:
            actor.apply_control(carla_module.WalkerControl(direction=carla_module.Vector3D(0, 0, 0), speed=0.0))
            return route_index
        route_index += 1
        target = route[route_index]
        delta_x, delta_y = float(target[0]) - location.x, float(target[1]) - location.y
        distance = math.hypot(delta_x, delta_y)
    if distance <= 0:
        raise ValueError("zero-length next route segment")
    speed = float(packet["walker_speed_mps"])
    actor.apply_control(carla_module.WalkerControl(direction=carla_module.Vector3D(delta_x / distance, delta_y / distance, 0), speed=speed))
    return route_index
