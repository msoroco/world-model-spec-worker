"""Native bicycle and four-source-camera setup for the speed comparison.

The caller must survey the actual map and stop-sign control before invoking
this module. A CPU mock proof checks API wiring; it is not a CARLA readback.
"""
from dataclasses import dataclass


BLUEPRINT = 'vehicle.bh.crossbike'
RATE_HZ = 20
FRAMES = 600
CAMERAS = (
    ('overview', 1920, 1080, 85, (-5.0, -12.0, 11.0), False),
    ('approach', 1280, 720, 80, (-7.0, 0.0, 3.0), True),
    ('reference_corner', 1280, 720, 80, (1.0, -6.0, 5.0), False),
    ('driver_reference', 1280, 720, 80, (0.8, 0.0, 1.5), True),
)
SPEED_REQUESTS = {'condition_a': 3.0, 'condition_b': 5.0}


@dataclass(frozen=True)
class Setup:
    bicycle: object
    cameras: dict
    requested_peak_speed_mps: float


def plan(condition):
    if condition not in SPEED_REQUESTS:
        raise ValueError('unknown speed condition')
    return {
        'condition': condition, 'actor_blueprint': BLUEPRINT,
        'requested_peak_speed_mps': SPEED_REQUESTS[condition],
        'start_xyz_m': (-50.0, -1.75, 0.7), 'yaw_deg': 0.0,
        'rate_hz': RATE_HZ, 'frames': FRAMES, 'duration_s': 30,
        'camera_profile': 'overview1080-capability',
        'cameras': [
            {'name': name, 'width': width, 'height': height, 'fov_deg': fov,
             'xyz_m': xyz, 'attach_to_bicycle': attached}
            for name, width, height, fov, xyz, attached in CAMERAS],
        'source_streams': {name: f'sources/cameras/{name}.mkv'
                           for name, *_ in CAMERAS},
        'native_conditions_unverified': True,
        'prudence_verdict_claimed': False,
    }


def setup(world, carla, request, survey):
    """Spawn owned actors after the caller's Native map/signal readback."""
    if request != plan(request.get('condition')):
        raise ValueError('bicycle capture plan changed')
    if not (survey.get('route_lane_verified') is True and
            survey.get('stop_sign_governs_route') is True and
            survey.get('approach_clearance_verified') is True):
        raise ValueError('Native route and stop-sign survey missing')
    owned = []
    try:
        library = world.get_blueprint_library()
        bicycle_bp = library.find(BLUEPRINT)
        bicycle_bp.set_attribute('role_name', 'c111325_bicycle_subject')
        x, y, z = request['start_xyz_m']
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(
            carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=request['yaw_deg'])))
        owned.append(bicycle)
        if bicycle.type_id != BLUEPRINT:
            raise ValueError('Native bicycle blueprint readback differs')
        cameras = {}
        for camera in request['cameras']:
            bp = library.find('sensor.camera.rgb')
            for key, value in (
                ('image_size_x', camera['width']), ('image_size_y', camera['height']),
                ('fov', camera['fov_deg']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            cx, cy, cz = camera['xyz_m']
            transform = carla.Transform(carla.Location(x=cx, y=cy, z=cz))
            sensor = world.spawn_actor(bp, transform,
                attach_to=bicycle if camera['attach_to_bicycle'] else None)
            owned.append(sensor)
            cameras[camera['name']] = sensor
        if set(cameras) != set(request['source_streams']):
            raise ValueError('four-camera source mapping changed')
        return Setup(bicycle, cameras, request['requested_peak_speed_mps'])
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise
