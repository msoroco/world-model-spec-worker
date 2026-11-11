"""Four original RGB source cameras for the C109749 left-turn construction."""
from contextlib import contextmanager

PROFILE = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


@contextmanager
def source_cameras(world, ego, transforms, plan):
    rows = {row['name']: row for row in plan}
    if set(rows) != set(PROFILE) or set(transforms) != set(PROFILE):
        raise ValueError('All four named source cameras required')
    sensors = {}
    try:
        for name, size in PROFILE.items():
            row = rows[name]
            if (row.get('width'), row.get('height')) != size:
                raise ValueError('Pinned source camera dimensions required')
            fov = row.get('fov_deg')
            if type(fov) not in (int, float) or not 30 <= fov <= 120:
                raise ValueError('Source camera FOV required')
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', size[0]), ('image_size_y', size[1]),
                               ('fov', fov), ('sensor_tick', 0.05)]:
                blueprint.set_attribute(key, str(value))
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
