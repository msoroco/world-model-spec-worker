"""Lazy CARLA construction and original local-road/control readback."""
from contextlib import contextmanager
import xml.etree.ElementTree as ET

from nonthrough_scene import validate


def require(value, message):
    if not value:
        raise ValueError(message)


def transform(carla, xyz, pitch=0, yaw=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=0))


def original_map_check(world, scene):
    """Reject lost signs, references or control inventory before recording."""
    xodr = world.get_map().to_opendrive()
    root = ET.fromstring(xodr)
    roads = {road.attrib.get('id'): road for road in root.findall('road')}
    require({'111325', '111326'} <= set(roads), 'CARLA map omitted local crossing roads')
    require(all('local_road' in roads[i].attrib.get('name', '') for i in ('111325', '111326')),
            'CARLA map changed local-road identity')
    subject_signals = roads['111325'].findall('signals/signal')
    counterpart_signals = roads['111326'].findall('signals/signal')
    governing = next((signal for signal in subject_signals
                      if signal.attrib.get('id') == scene['subject_governing_sign_id']), None)
    require(governing is not None, 'CARLA map omitted governing subject sign')
    require(governing.attrib.get('name') == scene['subject_control'].upper() and
            governing.attrib.get('orientation') == '+' and
            abs(float(governing.attrib.get('s', -100)) - 74) <= .01,
            'CARLA map changed subject sign or direction')
    expected_counterpart = scene['counterpart_control']
    if expected_counterpart == 'none':
        require(not counterpart_signals, 'CARLA map unexpectedly signs counterpart entrance')
    else:
        require(len(counterpart_signals) == 1 and
                counterpart_signals[0].attrib.get('name') == expected_counterpart.upper() and
                counterpart_signals[0].attrib.get('orientation') == '+',
                'CARLA map omitted counterpart entrance obligation')
    objects = roads['111325'].findall('objects/object')
    ref = scene['stop_reference']
    expected = 'marked-stop-line' if ref == 'stop_line' else 'near-side-crosswalk' if ref == 'crosswalk' else None
    if expected is None:
        require(not objects, 'CARLA map retained excluded stopping reference')
    else:
        require(len(objects) == 1 and objects[0].attrib.get('name') == expected,
                'CARLA map omitted stopping reference')
    signal = next((item for item in subject_signals
                   if item.attrib.get('id') == 'traffic-signal-111325'), None)
    require((signal is not None) == (scene['control_exception'] == 'signal'),
            'CARLA map signal exception differs')
    if signal is not None:
        require(signal.attrib.get('dynamic') == 'yes', 'CARLA map lost dynamic signal')
    return xodr


@contextmanager
def constructed_scene(client, carla, scene):
    """Construct requested actors and sources on an operator-owned server."""
    validate(scene)
    world = client.generate_opendrive_world(scene['road_opendrive'])
    original_map_check(world, scene)
    settings = world.get_settings()
    old_sync, old_delta = settings.synchronous_mode, settings.fixed_delta_seconds
    owned = []
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / scene['rate_hz']
        world.apply_settings(settings)
        current = world.get_settings()
        require(current.synchronous_mode and abs(current.fixed_delta_seconds - .05) <= 1e-6,
                'CARLA 20 Hz settings readback differs')
        library = world.get_blueprint_library()
        actors = {}
        for name in ('ego', 'counterpart'):
            spec = scene[name]
            actor = world.try_spawn_actor(library.find(spec['blueprint']),
                                          transform(carla, spec['start_xyz'], yaw=spec['heading_deg']))
            if actor is None:
                raise RuntimeError('CARLA participant spawn failed: ' + name)
            owned.append(actor)
            actors[name] = actor
        officer = None
        if scene['control_exception'] == 'police':
            matches = library.filter('walker.pedestrian.*')
            require(matches, 'No original officer actor blueprint available')
            officer = world.try_spawn_actor(matches[0], transform(carla, [-3, -5, .5]))
            if officer is None:
                raise RuntimeError('CARLA officer actor spawn failed')
            owned.append(officer)
        signal = None
        if scene['control_exception'] == 'signal':
            matches = [actor for actor in world.get_actors().filter('traffic.traffic_light*')
                       if actor.is_alive and abs(actor.get_location().x + 5) < 10 and
                       abs(actor.get_location().y + 3.7) < 10]
            require(len(matches) == 1, 'Exactly one original governing signal actor required')
            signal = matches[0]
        cameras = {}
        for spec in scene['cameras']:
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(spec['width']))
            blueprint.set_attribute('image_size_y', str(spec['height']))
            blueprint.set_attribute('fov', str(spec['fov_deg']))
            pose = transform(carla, spec['xyz'], pitch=spec['pitch'], yaw=spec['yaw'])
            sensor = (world.spawn_actor(blueprint, pose, attach_to=actors['ego'])
                      if spec.get('attach_to_ego') else world.spawn_actor(blueprint, pose))
            if sensor is None:
                raise RuntimeError('CARLA camera spawn failed: ' + spec['name'])
            owned.append(sensor)
            cameras[spec['name']] = sensor
        require(len(cameras) == 4, 'Four original cameras not constructed')
        yield {'world': world, 'ego': actors['ego'], 'counterpart': actors['counterpart'],
               'officer': officer, 'signal': signal, 'cameras': cameras,
               'map_opendrive': original_map_check(world, scene),
               'original_entrance_control_inventory_required': True}
    finally:
        for actor in reversed(owned):
            actor.destroy()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_delta
        world.apply_settings(settings)
