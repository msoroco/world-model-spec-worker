"""Four named source-camera actor construction at the pinned CPU profile.

Callers supply source-grounded static transforms for overview/approach/corner
and a relative driver transform. Real pixel coverage must be audited after run.
"""

from contextlib import contextmanager


SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


@contextmanager
def source_cameras(world, ego, transforms):
    if set(transforms) != set(SIZES):
        raise ValueError("All four named source-camera transforms required")
    sensors = {}
    try:
        for name, (width, height) in SIZES.items():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", "90")
            blueprint.set_attribute("sensor_tick", "0.05")
            kwargs = {"attach_to": ego} if name == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError("Native camera spawn failed: " + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()
