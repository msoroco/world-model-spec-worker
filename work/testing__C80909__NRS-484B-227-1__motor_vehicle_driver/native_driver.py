"""Lazy CARLA actor adapter for C80909 U-turn construction."""
from __future__ import annotations

import math

from uturn_control import apply, bind_map, next_request


def spawn_vehicle(world, scene, carla):
    mapping = world.get_map()
    endpoints = bind_map(mapping, scene, lambda x,y: carla.Location(x=x,y=y,z=0))
    selected = scene.get("vehicle_blueprint_id")
    if selected:
        blueprint = world.get_blueprint_library().find(selected)
        if blueprint is None:
            raise ValueError("reviewed Native vehicle blueprint is absent")
    else:
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("no conventional Native vehicle blueprint")
        blueprint = blueprints[0]
    blueprint.set_attribute("role_name", "c80909_227_1_ego")
    actor = world.spawn_actor(blueprint, endpoints[0].transform)
    if actor is None:
        raise ValueError("Native U-turn vehicle spawn failed")
    return actor


def spawn_observed_vehicle(world, scene, carla):
    """Place the fixed other-vehicle control on the opposite roadway."""
    spec = scene["observed_vehicle"]
    blueprint = world.get_blueprint_library().find(spec["blueprint_id"])
    if blueprint is None:
        raise ValueError("observed-vehicle Native blueprint is absent")
    blueprint.set_attribute("role_name", "c80909_227_1_observed")
    x, y = spec["position_xy_m"]
    transform = carla.Transform(carla.Location(x=x, y=y, z=spec["z_m"]),
                                carla.Rotation(yaw=spec["heading_deg"]))
    actor = world.spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("observed vehicle spawn failed")
    return actor


def body_polygon(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("original Native body lacks eight vertices")
    points = sorted({(float(point.x),float(point.y)) for point in vertices})
    if len(points) != 4 or not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("original Native body projection lacks four finite corners")
    center = (sum(x for x,_ in points)/4,sum(y for _,y in points)/4)
    return [list(point) for point in sorted(points,
        key=lambda point: math.atan2(point[1]-center[1],point[0]-center[0]))]


def original_sample(actor, snapshot, mapping=None):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    waypoint = mapping.get_waypoint(transform.location, project_to_road=False) if mapping is not None else None
    return {"frame": int(snapshot.frame), "time_s": float(snapshot.timestamp.elapsed_seconds),
            "actor_id": int(actor.id), "body_vertices_xy_m": body_polygon(actor),
            "road_id": int(waypoint.road_id) if waypoint is not None else None,
            "position_xy_m": [float(transform.location.x),float(transform.location.y)],
            "heading_deg": float(transform.rotation.yaw),
            "velocity_xy_mps": [float(velocity.x),float(velocity.y)],
            "speed_mps": speed}


def command_next_tick(actor, carla, scene, state, sample):
    request = next_request(scene,state,x=sample["position_xy_m"][0],
                           y=sample["position_xy_m"][1],
                           yaw_deg=sample["heading_deg"],speed_mps=sample["speed_mps"],
                           frame=sample["frame"])
    apply(actor,carla,request)
    return request
