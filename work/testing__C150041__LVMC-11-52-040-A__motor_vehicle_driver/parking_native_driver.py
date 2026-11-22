"""Lazy Native vehicle spawn at a source-bound draft pose."""
from __future__ import annotations

import math


def spawn_vehicle(world, scene, carla):
    blueprint_id = scene.get("vehicle_blueprint_id")
    if not blueprint_id:
        raise ValueError("exact vehicle blueprint ID required")
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None:
        raise ValueError("exact vehicle blueprint unavailable")
    center = scene["spawn_center_xy_m"]
    forward = scene["spawn_forward_xy"]
    yaw = math.degrees(math.atan2(forward[1], forward[0]))
    transform = carla.Transform(carla.Location(x=center[0], y=center[1], z=0.7),
                                carla.Rotation(yaw=yaw))
    vehicle = world.spawn_actor(blueprint, transform)
    if vehicle is None:
        raise RuntimeError("exact parking vehicle spawn failed")
    try:
        extent = vehicle.bounding_box.extent
        expected = scene["vehicle_dimensions_request_m"]
        if (abs(2 * extent.x - expected["length"]) > .75 or
                abs(2 * extent.y - expected["width"]) > .5):
            raise ValueError("Native vehicle body differs from full-footprint request")
        actual = vehicle.get_transform()
        if (math.dist((actual.location.x, actual.location.y), center) > .5 or
                abs((actual.rotation.yaw - yaw + 180) % 360 - 180) > 5):
            raise ValueError("Native vehicle spawn pose readback differs")
        return vehicle
    except BaseException:
        vehicle.destroy()
        raise
