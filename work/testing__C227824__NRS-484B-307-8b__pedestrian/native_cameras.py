"""Spawn four reviewed C227824 source cameras on a CARLA world."""
from __future__ import annotations

import math

from native_recorder import SIZES
from saved_entry import CAMERAS


def _xyz(point):
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError("reviewed camera location/target must be xyz")
    values = tuple(float(value) for value in point)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("nonfinite reviewed camera location/target")
    return values


def placements(scene):
    review = scene.get("camera_placement_review")
    if not isinstance(review, dict) or review.get("complete") is not True:
        raise ValueError("complete original camera placement review missing")
    digest = review.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("original camera placement source hash missing")
    cameras = scene.get("camera_placements")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four reviewed camera placements required")
    result = {}
    for name in CAMERAS:
        item = cameras[name]
        if not isinstance(item, dict):
            raise ValueError("reviewed camera placement missing: " + name)
        x, y, z = _xyz(item.get("location_xyz_m"))
        tx, ty, tz = _xyz(item.get("target_xyz_m"))
        distance = math.hypot(tx - x, ty - y)
        if distance <= .1 or z <= .2:
            raise ValueError("degenerate original camera aim: " + name)
        yaw = math.degrees(math.atan2(ty - y, tx - x))
        pitch = math.degrees(math.atan2(tz - z, distance))
        result[name] = ((x, y, z), (pitch, yaw))
    return result


def spawn(world, carla, scene):
    """Construct four RGB sensors; destroy partial spawns on failure."""
    sites = placements(scene)
    sensors = {}
    try:
        for name in CAMERAS:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            if blueprint is None:
                raise ValueError("Native RGB camera blueprint missing")
            width, height = SIZES[name]
            for key, value in (("image_size_x", width), ("image_size_y", height), ("fov", 75)):
                blueprint.set_attribute(key, str(value))
            (x, y, z), (pitch, yaw) = sites[name]
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=pitch, yaw=yaw))
            sensor = world.spawn_actor(blueprint, transform)
            if sensor is None:
                raise ValueError("Native RGB camera spawn failed: " + name)
            sensors[name] = sensor
        return sensors
    except BaseException:
        for sensor in reversed(list(sensors.values())):
            sensor.destroy()
        raise
