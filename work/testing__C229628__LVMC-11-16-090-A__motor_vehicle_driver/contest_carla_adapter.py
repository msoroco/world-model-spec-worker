"""Lazy CARLA adapter for two source-identified motor vehicles and four cameras."""
import io
import math
from queue import Queue

from native_source import CAMERAS


def need(ok, message):
    if not ok:
        raise ValueError(message)


class CarlaContestAdapter:
    native_attested = True

    def __init__(self, host, port, site):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.site = site
        need(self.world.get_map().name == site['map_name'], 'reviewed Native map differs')
        self.old_settings = self.world.get_settings()
        self.owned = []
        self.routes = {}
        self.cameras = {}
        self.queues = {}
        self.ego = None
        self.other = None
        self.cue_frame = None
        self.other_start_frame = None
        self.cue_enabled = False
        self.contest_candidate = False
        self.index = 0
        self.first_native_frame = None

    def prepare(self):
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        need(self.world.get_settings().synchronous_mode and
             abs(self.world.get_settings().fixed_delta_seconds - .05) < 1e-6,
             'Native 20 Hz settings readback failed')

    def spawn_vehicle(self, xy):
        carla = self.carla
        blueprint_id = self.site.get('vehicle_blueprint_id', 'vehicle.tesla.model3')
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        need(blueprint.id.startswith('vehicle.'), 'motor vehicle blueprint required')
        waypoint = self.world.get_map().get_waypoint(carla.Location(x=xy[0], y=xy[1]),
                                                     project_to_road=False)
        need(waypoint is not None, 'source route start is not on Native roadway')
        actor = self.world.try_spawn_actor(blueprint, waypoint.transform)
        need(actor is not None, 'Native motor vehicle spawn failed')
        self.owned.append(actor)
        if self.ego is None:
            self.ego = actor
        elif self.other is None:
            self.other = actor
        return actor

    def set_route(self, actor, points):
        carla = self.carla
        route = []
        for x, y in points:
            waypoint = self.world.get_map().get_waypoint(
                carla.Location(x=x, y=y), project_to_road=False)
            need(waypoint is not None, 'reviewed route leaves Native roadway')
            route.append(carla.Location(x=x, y=y, z=waypoint.transform.location.z))
        need(len(route) >= 2, 'connected route missing')
        self.routes[actor.id] = {'points': route, 'index': 1}

    def set_start_cue(self, actor, frame, enabled):
        need(actor is self.ego and type(frame) is int, 'ego cue identity changed')
        self.cue_frame = frame
        self.cue_enabled = enabled

    def set_other_start(self, actor, frame, candidate):
        need(actor is self.other and type(frame) is int, 'other start identity changed')
        self.other_start_frame = frame
        self.contest_candidate = candidate

    def attach_cameras(self):
        need(self.ego is not None and self.other is not None, 'two Native vehicles required')
        carla = self.carla
        locations = {'overview': (-17, 0, 20), 'approach': (0, 0, 5),
                     'reference_corner': (-6, 2, 3),
                     'driver_reference': (-6, -2, 3)}
        for name in CAMERAS:
            blueprint = self.world.get_blueprint_library().find('sensor.camera.rgb')
            width, height = ((1920, 1080) if name == 'overview' else (1280, 720))
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '0.05')
            parent = self.other if name == 'driver_reference' else self.ego
            camera = self.world.spawn_actor(
                blueprint, carla.Transform(carla.Location(*locations[name])), attach_to=parent)
            queue = Queue()
            camera.listen(queue.put)
            self.owned.append(camera)
            self.cameras[name] = camera
            self.queues[name] = queue

    def _control(self, actor, speed_target):
        route = self.routes[actor.id]
        here = actor.get_location()
        while route['index'] + 1 < len(route['points']) and \
                here.distance(route['points'][route['index']]) < 6:
            route['index'] += 1
        target = route['points'][route['index']]
        yaw = actor.get_transform().rotation.yaw
        desired = math.degrees(math.atan2(target.y - here.y, target.x - here.x))
        error = (desired - yaw + 180) % 360 - 180
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        actor.apply_control(self.carla.VehicleControl(
            throttle=max(0, min(.7, (speed_target - speed) * .18)),
            brake=max(0, min(1, (speed - speed_target) * .35)),
            steer=max(-.7, min(.7, error / 42))))

    def tick(self, index):
        need(self.ego is not None and self.other is not None, 'two Native vehicles required')
        self.index = index
        if self.cue_enabled and index in (self.cue_frame, self.cue_frame + 1):
            state = (self.carla.VehicleLightState.HighBeam if index == self.cue_frame
                     else self.carla.VehicleLightState.NONE)
            self.ego.set_light_state(self.carla.VehicleLightState(state))
        ego_target = 7.0
        other_target = 0.0 if index < self.other_start_frame else \
            (10.0 if self.contest_candidate else 5.0)
        self._control(self.ego, ego_target)
        self._control(self.other, other_target)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(frame == snapshot.frame, 'Native snapshot frame differs')
        if self.first_native_frame is None:
            self.first_native_frame = frame
        need(frame == self.first_native_frame + index, 'Native frame discontinuity')
        return frame, snapshot.timestamp.elapsed_seconds

    def read(self, index, native_frame, time_s, scene, case):
        def speed(actor):
            velocity = actor.get_velocity()
            return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        def accel(actor):
            value = actor.get_acceleration()
            return math.sqrt(value.x ** 2 + value.y ** 2 + value.z ** 2)
        ego_pos, other_pos = self.ego.get_location(), self.other.get_location()
        cue_readback = bool(self.ego.get_light_state() &
                            self.carla.VehicleLightState.HighBeam)
        need(cue_readback == bool(case.cue and index == self.cue_frame),
             'Native assistance cue light readback differs')
        row = {'original_frame': index, 'native_frame': native_frame,
               'time_s': index / 20, 'native_time_s': time_s,
               'ego_xy': [ego_pos.x, ego_pos.y],
               'other_xy': [other_pos.x, other_pos.y],
               'ego_speed_mps': speed(self.ego), 'other_speed_mps': speed(self.other),
               'ego_accel_mps2': accel(self.ego),
               'other_accel_mps2': accel(self.other),
               'cue_observed': cue_readback,
               'highway': case.highway,
               'candidate_contest': case.candidate_contest,
               'ego_actor_id': str(self.ego.id), 'other_actor_id': str(self.other.id)}
        for name in ('ego_person_id', 'other_person_id', 'ego_vehicle_id', 'other_vehicle_id'):
            row[name] = scene[name]
        for name in scene:
            if name.endswith('_source_sha256'):
                row[name] = scene[name]
        return row

    def pixels(self, native_frame):
        from PIL import Image
        images = {}
        for name in CAMERAS:
            image = self.queues[name].get(timeout=10)
            need(image.frame == native_frame, 'camera frame mismatch: ' + name)
            raster = Image.frombytes('RGBA', (image.width, image.height),
                                     bytes(image.raw_data), 'raw', 'BGRA')
            stream = io.BytesIO()
            raster.convert('RGB').save(stream, format='PNG')
            images[name] = stream.getvalue()
        return images

    def destroy(self, actor):
        actor.destroy()

    def cleanup(self):
        try:
            for actor in (self.ego, self.other):
                if actor is not None:
                    actor.apply_control(self.carla.VehicleControl(throttle=0, brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.owned.clear()
            self.world.apply_settings(self.old_settings)
            restored = self.world.get_settings()
            need(restored.synchronous_mode == self.old_settings.synchronous_mode,
                 'Native world restoration failed')
