"""Proposed Native left-turn signal capture setup; no physical claim."""
from dataclasses import dataclass


RATE_HZ = 20
FRAMES = 600
BLUEPRINT = 'vehicle.tesla.model3'
SIGNAL_REQUEST_M = {'other_long': 100.0, 'other_short': 70.0,
                    'district_long': 35.2, 'district_short': 20.0}
CAMERAS = (
    ('overview', 1920, 1080, (-8.0, -10.0, 12.0), False),
    ('approach', 1280, 720, (-6.0, 0.0, 3.0), True),
    ('reference_corner', 1280, 720, (1.0, -6.0, 5.0), False),
    ('driver_reference', 1280, 720, (0.9, 0.0, 1.5), True),
)


@dataclass(frozen=True)
class Setup:
    ego: object
    cameras: dict
    requested_signal_distance_m: float


def plan(condition):
    if condition not in SIGNAL_REQUEST_M:
        raise ValueError('unknown signal distance condition')
    district = 'other_area' if condition.startswith('other_') else 'business_or_residential'
    weather = 'clear' if district == 'other_area' else 'rain'
    return {'condition': condition, 'actor_blueprint': BLUEPRINT,
            'district_class': district, 'weather': weather,
            'requested_signal_distance_m': SIGNAL_REQUEST_M[condition],
            'rate_hz': RATE_HZ, 'frames': FRAMES, 'duration_s': 30,
            'maneuver': 'left_turn', 'layout': 'median_opening',
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'xyz_m': xyz, 'attach_to_ego': attached}
                        for name, width, height, xyz, attached in CAMERAS],
            'source_streams': {name: 'sources/cameras/'+name+'.mkv'
                               for name, *_ in CAMERAS},
            'district_weather_native_verified': False,
            'visible_signal_pixels_verified': False,
            'legal_verdict_claimed': False}


def setup(world, carla, request, survey):
    if request != plan(request.get('condition')):
        raise ValueError('turn capture plan changed')
    if not (survey.get('median_opening_verified') is True and
            survey.get('incoming_lane_verified') is True and
            survey.get('turn_route_verified') is True and
            survey.get('district_class') == request['district_class'] and
            survey.get('weather') == request['weather']):
        raise ValueError('Native turn/district/weather survey missing')
    owned = []
    try:
        library = world.get_blueprint_library()
        bp = library.find(BLUEPRINT)
        bp.set_attribute('role_name', 'c124163_turn_subject')
        ego = world.spawn_actor(bp, carla.Transform(carla.Location(x=-120, y=0, z=0.7)))
        owned.append(ego)
        if ego.type_id != BLUEPRINT:
            raise ValueError('Native actor blueprint readback differs')
        cameras = {}
        for camera in request['cameras']:
            sensor_bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', camera['width']),
                               ('image_size_y', camera['height']),
                               ('sensor_tick', 0)):
                sensor_bp.set_attribute(key, str(value))
            x, y, z = camera['xyz_m']
            sensor = world.spawn_actor(sensor_bp,
                carla.Transform(carla.Location(x=x, y=y, z=z)),
                attach_to=ego if camera['attach_to_ego'] else None)
            owned.append(sensor)
            cameras[camera['name']] = sensor
        if set(cameras) != set(request['source_streams']):
            raise ValueError('Camera source map changed')
        return Setup(ego, cameras, request['requested_signal_distance_m'])
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise
