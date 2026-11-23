"""Lazy CARLA placement and release controller for the C125763 timing probes.

The requested release offset is an engineering target. Measured entry timestamps
come only from crossing_timing.py over original recorded body histories.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_scene(packet_path, world):
    path = Path(packet_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Reviewed site packet absent or symlinked")
    scene = json.loads(path.read_text())
    road = world.get_map().to_opendrive()
    if hashlib.sha256(road.encode()).hexdigest() != scene.get("map_sha256"):
        raise ValueError("Live OpenDRIVE differs from reviewed site map")
    required = ("reviewer", "source_citation", "device_source", "highway_source",
                "ego_route", "other_route", "ego_blueprint", "other_blueprint")
    if any(not scene.get(key) for key in required):
        raise ValueError("Reviewed construction source is incomplete")
    for source_name in ("device_source", "highway_source"):
        source = scene[source_name]
        source_path = path.parent / source["path"]
        if (source_path.is_symlink() or not source_path.is_file() or
                not source_path.resolve().is_relative_to(path.parent.resolve()) or
                _sha(source_path) != source.get("sha256") or not source.get("citation")):
            raise ValueError("Reviewed " + source_name + " original bytes absent or stale")
    if (scene.get("cell_id") != "C125763" or scene.get("control") != "yield_sign"
            or scene.get("ego_highway") == scene.get("other_highway")
            or scene.get("approach_relation") != "crossing"
            or scene.get("ego_side") not in ("left", "right")):
        raise ValueError("Reviewed construction is not the fixed C125763 crossing")
    for name in ("ego_route", "other_route"):
        route = scene[name]
        if len(route) < 2 or any(len(p) != 3 or not all(math.isfinite(x) for x in p) for p in route):
            raise ValueError("Reviewed " + name + " is not a finite 3D route")
        if math.dist(route[0], route[1]) < 1:
            raise ValueError("Reviewed " + name + " has no approach heading")
    return scene


def _transform(carla, route):
    start, next_point = route[:2]
    yaw = math.degrees(math.atan2(next_point[1] - start[1], next_point[0] - start[0]))
    return carla.Transform(carla.Location(x=start[0], y=start[1], z=start[2]),
                           carla.Rotation(yaw=yaw))


def spawn_pair(world, carla, scene):
    """Spawn both reviewed approach directions; caller owns destruction/restore."""
    actors = []
    try:
        for name in ("ego", "other"):
            route = scene[name + "_route"]
            location = carla.Location(x=route[0][0], y=route[0][1], z=route[0][2])
            lane = world.get_map().get_waypoint(location, project_to_road=False)
            expected = scene[name + "_lane"]
            if lane is None or (lane.road_id, lane.lane_id) != (expected["road_id"], expected["lane_id"]):
                raise ValueError(name + " reviewed approach lane does not match live map")
            blueprint = world.get_blueprint_library().find(scene[name + "_blueprint"])
            actor = world.try_spawn_actor(blueprint, _transform(carla, route))
            if actor is None:
                raise RuntimeError(name + " spawn failed")
            actors.append(actor)
        return tuple(actors)
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def control_step(carla, actor, route, now_s, release_s, target_speed_mps=8.0):
    """Apply bounded route-heading control; never relocate the vehicle."""
    if now_s < release_s:
        actor.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
        return "held"
    location = actor.get_location()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    target = min(route[1:], key=lambda point: math.hypot(point[0] - location.x, point[1] - location.y))
    desired = math.atan2(target[1] - location.y, target[0] - location.x)
    heading = math.radians(actor.get_transform().rotation.yaw)
    error = math.atan2(math.sin(desired - heading), math.cos(desired - heading))
    steer = max(-1.0, min(1.0, error / .5))
    throttle = max(0.0, min(.55, .25 * (target_speed_mps - speed)))
    brake = max(0.0, min(.8, .2 * (speed - target_speed_mps)))
    actor.apply_control(carla.VehicleControl(throttle=throttle, steer=steer, brake=brake))
    return "released"
