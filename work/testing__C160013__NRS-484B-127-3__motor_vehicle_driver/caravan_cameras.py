"""Four synchronized original RGB viewpoints for the Native caravan."""
from contextlib import contextmanager

PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


@contextmanager
def source_cameras(world, entrant, transforms):
    if set(transforms) != set(PROFILE):
        raise ValueError("Four reviewed source camera poses required")
    sensors = {}
    try:
        for name, (width, height) in PROFILE.items():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 90), ("sensor_tick", .05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {"attach_to": entrant} if name == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError("Native source camera spawn failed: " + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()
