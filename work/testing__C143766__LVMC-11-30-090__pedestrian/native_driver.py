"""Lazy CARLA-facing walker request for the authored corridor candidate."""
from __future__ import annotations

import math
import hashlib

from corridor_construction import request_next_target, validate_scene

LANE_IDS = {"roadway": -1, "shoulder": -2, "sidewalk": -3}


def bind_map(world_map, scene, location_factory, lane_type_any):
    """Reject an unreviewed map or wrong lane before a walker is spawned."""
    validate_scene(scene)
    if hashlib.sha256(world_map.to_opendrive().encode()).hexdigest() != scene["map_source_sha256"]:
        raise ValueError("live OpenDRIVE source differs from authored candidate")
    waypoints = []
    for x, y in scene["pedestrian_route_xy_m"]:
        waypoint = world_map.get_waypoint(location_factory(x, y),
                                          project_to_road=False, lane_type=lane_type_any)
        if waypoint is None:
            raise ValueError("pedestrian route point has no Native waypoint")
        if waypoint.road_id != 1 or waypoint.lane_id != LANE_IDS[scene["route_band"]]:
            raise ValueError("pedestrian route point maps to wrong roadway or lane band")
        location = waypoint.transform.location
        if math.hypot(location.x-x, location.y-y) > .5:
            raise ValueError("pedestrian route point is too far from Native waypoint")
        waypoints.append(waypoint)
    return waypoints


def spawn_walker(world, scene, carla):
    """Spawn the exact pedestrian actor only after all map anchors bind."""
    waypoints = bind_map(world.get_map(), scene,
                         lambda x, y: carla.Location(x=x, y=y, z=.1), carla.LaneType.Any)
    blueprints = world.get_blueprint_library().filter("walker.pedestrian.*")
    if not blueprints:
        raise ValueError("No Native pedestrian blueprint")
    actor = world.spawn_actor(blueprints[0], waypoints[0].transform)
    if actor is None:
        raise ValueError("Native pedestrian spawn failed")
    return actor


def apply_walker_request(actor, carla, scene, target_index=1):
    """Send a next-tick request based on the original current walker pose."""
    validate_scene(scene)
    pose = actor.get_transform()
    x, y = float(pose.location.x), float(pose.location.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("missing original walker pose")
    request = request_next_target(scene, x, y, target_index)
    dx, dy = request["direction_xy"]
    actor.apply_control(carla.WalkerControl(
        direction=carla.Vector3D(x=dx, y=dy, z=0), speed=request["speed_mps"], jump=False))
    return request
