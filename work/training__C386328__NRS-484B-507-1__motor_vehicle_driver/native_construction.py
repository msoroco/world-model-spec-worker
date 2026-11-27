"""Lazy original Native freight-zone construction and actor ownership."""
from contextlib import contextmanager
import xml.etree.ElementTree as ET

from freight_scene import CAMERAS, ROAD_ID, validate_request


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw))


def checked_map(world, scene):
    source = world.get_map().to_opendrive()
    root = ET.fromstring(source)
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('id') != str(ROAD_ID):
        raise ValueError('original one-way freight road differs')
    curb = roads[0].find('objects/object')
    sign = roads[0].find('signals/signal')
    if curb is None or curb.get('id') != scene['zone']['object_id'] or curb.get('type') != 'curb':
        raise ValueError('original marked freight curb differs')
    if sign is None or sign.get('id') != scene['zone']['sign_id'] or not all(
            token in sign.get('name', '') for token in ('08:00', '17:00', 'America/Los_Angeles')):
        raise ValueError('original freight sign or authored hours differ')
    return source


@contextmanager
def constructed_scene(client, carla, scene):
    validate_request(scene)
    world = client.generate_opendrive_world(scene['road_opendrive'])
    source = checked_map(world, scene)
    settings = world.get_settings()
    prior_sync, prior_delta = settings.synchronous_mode, settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        readback = world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-6:
            raise ValueError('original 20 Hz timing readback differs')
        library = world.get_blueprint_library()
        def spawn(blueprint, xyz, yaw=0):
            actor = world.try_spawn_actor(library.find(blueprint), transform(carla, xyz, yaw=yaw))
            if actor is None:
                raise RuntimeError('original freight-zone actor spawn failed: ' + blueprint)
            owned.append(actor)
            return actor
        ego = spawn(scene['vehicle']['blueprint'], [-32, -2.3, .5])
        material = spawn(scene['material']['blueprint'], scene['material']['source_and_destination_xyz'][0])
        sign = spawn(scene['sign']['blueprint'], scene['sign']['xyz'])
        passenger = None
        if scene['passenger']['requested_activity'] != 'none_requested':
            walkers = library.filter('walker.pedestrian.*')
            if not walkers:
                raise RuntimeError('original passenger blueprint unavailable')
            passenger = world.try_spawn_actor(walkers[0], transform(carla, [0, -6, .5]))
            if passenger is None:
                raise RuntimeError('original passenger spawn failed')
            owned.append(passenger)
        waiting = None
        if scene['material_transport_vehicle']['requested_waiting_to_enter']:
            waiting = spawn(scene['material_transport_vehicle']['blueprint'],
                            scene['material_transport_vehicle']['requested_xyz'])
        cameras = {}
        for spec in scene['cameras']:
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['size'][0]))
            bp.set_attribute('image_size_y', str(spec['size'][1]))
            bp.set_attribute('fov', '80')
            sensor = world.spawn_actor(bp, transform(carla, spec['xyz'], spec['pitch'], spec['yaw']),
                                       attach_to=ego if spec.get('attach_to_vehicle') else None)
            if sensor is None:
                raise RuntimeError('original camera spawn failed: ' + spec['name'])
            owned.append(sensor)
            cameras[spec['name']] = sensor
        if set(cameras) != CAMERAS:
            raise ValueError('four original source cameras missing')
        yield {'world': world, 'ego': ego, 'material': material, 'sign': sign,
               'passenger': passenger, 'waiting_vehicle': waiting, 'cameras': cameras,
               'map_opendrive': checked_map(world, scene), 'zone_authority_observed': False,
               'material_transfer_observed': False, 'passenger_transfer_observed': False,
               'interference_observed': False}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode, settings.fixed_delta_seconds = prior_sync, prior_delta
        world.apply_settings(settings)
