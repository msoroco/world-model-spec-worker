"""CARLA construction calls for the C177225 directed-stop rail approach.

This module only builds the requested scene. The eventual runner must retain
Native map, actor, signal and camera readback before judging any observation.
"""
from dataclasses import dataclass

from officer_direction import Crossing


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


@dataclass(frozen=True)
class SceneAssets:
    rail_asset_blueprint: str
    officer_blueprint: str = 'walker.pedestrian.0001'
    bus_blueprint: str = 'vehicle.mitsubishi.fusorosa'

    def validate(self):
        if not self.rail_asset_blueprint.startswith('static.prop.'):
            raise ValueError('Actual rail crossing prop blueprint is required')
        if not self.officer_blueprint.startswith('walker.pedestrian.'):
            raise ValueError('An officer actor blueprint is required')
        if self.bus_blueprint != 'vehicle.mitsubishi.fusorosa':
            raise ValueError('Exact motor bus blueprint changed')


def camera_plan(direction):
    if direction not in (-1, 1):
        raise ValueError('Invalid rail approach direction')
    return (
        {'name': 'overview', 'xyz': (-18 * direction, -12, 24),
         'yaw': 35 if direction == 1 else 145, 'pitch': -50,
         'fov': 85, 'size': (1280, 720), 'attach_to_bus': False},
        {'name': 'approach', 'xyz': (-42 * direction, -7, 8),
         'yaw': 0 if direction == 1 else 180, 'pitch': -16,
         'fov': 72, 'size': (1280, 720), 'attach_to_bus': False},
        {'name': 'reference_corner', 'xyz': (8 * direction, 10, 8),
         'yaw': 180 if direction == 1 else 0, 'pitch': -20,
         'fov': 75, 'size': (1280, 720), 'attach_to_bus': False},
        {'name': 'driver_reference', 'xyz': (1, 0, 2.6),
         'yaw': 0, 'pitch': -8, 'fov': 90, 'size': (1280, 720),
         'attach_to_bus': True},
    )


def _transform(carla, xyz, yaw=0, pitch=0):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def spawn_scene(world, carla, layout, assets, *, direction, camera_width_m=7.0):
    """Spawn bus, officer, two rail assets and all four camera sources.

    The caller owns and must destroy every returned actor. The exact installed
    rail prop ID must be supplied and checked; there is no invisible rail flag.
    """
    layout.validate()
    assets.validate()
    if direction not in (-1, 1):
        raise ValueError('Invalid rail approach direction')
    if camera_width_m <= 0:
        raise ValueError('Camera coverage width must be positive')
    blueprint_library = world.get_blueprint_library()
    road_map = world.get_map()
    start_x = layout.approach_station(direction)
    stop_x = layout.stop_station(direction)
    lane_y = -1.75 * direction
    for x in (start_x, stop_x):
        waypoint = road_map.get_waypoint(carla.Location(x=x, y=lane_y, z=0),
                                        project_to_road=False,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None:
            raise ValueError('Bus route lacks Native driving lane at approach or stop')
    owned = []
    try:
        bus_bp = blueprint_library.find(assets.bus_blueprint)
        bus_bp.set_attribute('role_name', 'c177225_bus')
        bus = world.spawn_actor(bus_bp, _transform(carla, (start_x, lane_y, 0.5),
                                                   yaw=0 if direction == 1 else 180))
        owned.append(bus)
        if bus.bounding_box.extent.x * 2 > layout.exit_clearance_m:
            raise ValueError('Native bus is longer than rail exit clearance')
        officer_bp = blueprint_library.find(assets.officer_blueprint)
        officer_bp.set_attribute('role_name', 'c177225_directing_officer')
        officer = world.spawn_actor(officer_bp,
                                    _transform(carla, (stop_x,
                                                       -direction * (camera_width_m / 2 + 1), 0.2),
                                               yaw=90 if direction == 1 else -90))
        owned.append(officer)
        rail_bp = blueprint_library.find(assets.rail_asset_blueprint)
        rail_bp.set_attribute('role_name', 'c177225_rail_asset')
        rails = []
        for x in (layout.track_center_m - layout.track_half_width_m,
                  layout.track_center_m + layout.track_half_width_m):
            rail = world.spawn_actor(rail_bp, _transform(carla, (x, 0, 0)))
            owned.append(rail)
            rails.append(rail)
        cameras = {}
        for spec in camera_plan(direction):
            bp = blueprint_library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['size'][0]),
                               ('image_size_y', spec['size'][1]),
                               ('fov', spec['fov']), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            kwargs = {'attach_to': bus} if spec['attach_to_bus'] else {}
            camera = world.spawn_actor(bp, _transform(carla, spec['xyz'],
                                                       spec['yaw'], spec['pitch']),
                                       **kwargs)
            owned.append(camera)
            cameras[spec['name']] = camera
        return {'bus': bus, 'officer': officer, 'rails': tuple(rails),
                'cameras': cameras, 'owned': tuple(owned),
                'requested_bus_start_x_m': start_x,
                'requested_stop_x_m': stop_x,
                'requested_driving_lane_center_y_m': lane_y,
                'source_kind': 'authored_scene_request',
                'physical_success_claimed': False}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise
