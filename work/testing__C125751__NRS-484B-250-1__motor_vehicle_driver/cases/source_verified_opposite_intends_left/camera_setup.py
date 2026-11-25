"""Four named source-camera actors for the inoperative median crossing.

Static poses come from the selected site; actual participant and signal-head
pixel coverage is measured after capture.
"""
from contextlib import contextmanager


PROFILE = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


@contextmanager
def source_cameras(world, ego, transforms):
    if set(transforms) != set(PROFILE):
        raise ValueError('All four named source-camera transforms required')
    sensors = {}
    try:
        for name, (width, height) in PROFILE.items():
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            if blueprint is None:
                raise ValueError('Native RGB camera blueprint missing')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', '90')
            blueprint.set_attribute('sensor_tick', '0.05')
            kwargs = {'attach_to': ego} if name == 'driver_reference' else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError('Native camera spawn failed: ' + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()
