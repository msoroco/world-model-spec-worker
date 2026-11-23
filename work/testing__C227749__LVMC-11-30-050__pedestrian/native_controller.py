"""Lazy CARLA walker construction for authored pedestrian route targets."""
from __future__ import annotations

import math

from crossing_geometry import validate_scene, point


def spawn_walker(world, carla, scene, blueprint_id='walker.pedestrian.0001'):
    validate_scene(scene)
    blueprints = world.get_blueprint_library()
    blueprint = blueprints.find(blueprint_id)
    x, y = point(scene['route_xy_m'][0])
    location = carla.Location(x=x, y=y, z=float(scene.get('spawn_height_m', 0.3)))
    actor = world.try_spawn_actor(blueprint, carla.Transform(location))
    if actor is None:
        raise RuntimeError('pedestrian spawn failed')
    got = actor.get_transform().location
    if math.dist((got.x, got.y), (x, y)) > 0.5:
        actor.destroy()
        raise RuntimeError('walker spawn readback outside engineering tolerance')
    return actor


def request_next_control(actor, carla, scene, target_index, speed_mps=1.2):
    """Request motion only; actual progress must come from original body history."""
    validate_scene(scene)
    route = [point(p) for p in scene['route_xy_m']]
    if not 1 <= target_index < len(route):
        raise ValueError('target index out of range')
    loc = actor.get_transform().location
    at = (float(loc.x), float(loc.y))
    if math.dist(at, route[target_index]) <= 0.4 and target_index + 1 < len(route):
        target_index += 1
    target = route[target_index]
    dx, dy = target[0]-at[0], target[1]-at[1]
    distance = math.hypot(dx, dy)
    if not math.isfinite(distance) or not math.isfinite(speed_mps) or speed_mps <= 0:
        raise ValueError('invalid walker target or speed')
    speed = 0.0 if distance <= 0.15 else float(speed_mps)
    direction = carla.Vector3D(x=dx/distance, y=dy/distance, z=0) if distance else carla.Vector3D(x=0,y=0,z=0)
    control = carla.WalkerControl(direction=direction, speed=speed, jump=False)
    actor.apply_control(control)
    return target_index
