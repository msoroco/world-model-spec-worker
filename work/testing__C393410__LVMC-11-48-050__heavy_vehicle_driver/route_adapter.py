"""Bounded Native heavy-vehicle motion and original road/vehicle readback."""
from __future__ import annotations

import math


def configure(world, carla, packet: dict, speed_mps: float) -> dict:
    itinerary = packet["itinerary"]
    points = itinerary["waypoints_xy_m"]
    spawn = itinerary["spawn_xyz_m"]
    blueprint = world.get_blueprint_library().find(packet["vehicle"]["blueprint"])
    if blueprint is None or not blueprint.id.startswith("vehicle."):
        raise ValueError("Reviewed heavy vehicle blueprint unavailable")
    yaw = math.degrees(math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0]))
    pose = carla.Transform(carla.Location(x=float(spawn[0]), y=float(spawn[1]), z=float(spawn[2])), carla.Rotation(yaw=yaw))
    vehicle = world.try_spawn_actor(blueprint, pose)
    if vehicle is None or not vehicle.type_id.startswith("vehicle."):
        raise RuntimeError("Original heavy vehicle spawn failed")
    vehicle.set_autopilot(False)
    return {"vehicle": vehicle, "points": points, "next_index": 1, "speed_mps": float(speed_mps)}


def step(handle: dict, carla) -> None:
    vehicle = handle["vehicle"]
    points = handle["points"]
    index = handle["next_index"]
    location = vehicle.get_transform().location
    while index < len(points) - 1 and math.hypot(points[index][0] - location.x, points[index][1] - location.y) < 3.0:
        index += 1
    handle["next_index"] = index
    target = points[index]
    desired = math.degrees(math.atan2(target[1] - location.y, target[0] - location.x))
    yaw = vehicle.get_transform().rotation.yaw
    error = (desired - yaw + 180.0) % 360.0 - 180.0
    velocity = vehicle.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    wanted = handle["speed_mps"]
    throttle = max(0.0, min(.55, .24 * (wanted - speed)))
    brake = 0.0 if speed <= wanted else min(.5, .18 * (speed - wanted))
    vehicle.apply_control(carla.VehicleControl(throttle=throttle, steer=max(-.8, min(.8, error / 45.0)), brake=brake))


def sample(world, handle: dict, packet: dict, frame: int, time_s: float) -> dict:
    vehicle = handle["vehicle"]
    if not vehicle.is_alive:
        raise RuntimeError("Original heavy vehicle no longer alive")
    position = vehicle.get_transform().location
    waypoint = world.get_map().get_waypoint(position, project_to_road=False)
    if waypoint is None:
        raise ValueError("Original heavy vehicle outside reviewed roadway")
    street = packet["site"]["traveled_street"]
    road_id = int(waypoint.road_id)
    if road_id != street["road_id"]:
        raise ValueError("Original heavy vehicle reached unreviewed road identity")
    return {"frame": int(frame), "time_s": float(time_s), "ego_actor_id": int(vehicle.id),
        "position_xy_m": [float(position.x), float(position.y)], "road_id": road_id,
        "street_designation": street["designation"], "vehicle_identity": packet["vehicle"]["identity"],
        "observation_source": "original_native_snapshot"}


def teardown(handle: dict) -> None:
    vehicle = handle["vehicle"]
    if vehicle.is_alive:
        vehicle.destroy()
