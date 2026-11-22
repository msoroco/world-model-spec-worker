"""Lazy original Native capture for C101303 following before lane change."""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from construction import speed_command
from following import body_gap
from native_route import discover_hill_route
from native_samples import sample


CAMERAS = (('overview', 1920, 1080, (0, 0, 45, -90)),
           ('approach', 1280, 720, (-15, -12, 12, -25)),
           ('reference_corner', 1280, 720, (4, 4, 12, -45)),
           ('driver_reference', 1280, 720, (0, 0, 2, 0)))


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


def _steer(actor, waypoint):
    transform = actor.get_transform()
    location = transform.location
    target = waypoint.transform.location
    desired = math.degrees(math.atan2(target.y-location.y, target.x-location.x))
    error = (desired-transform.rotation.yaw+180)%360-180
    return max(-.8, min(.8, error/35))


def _ahead(waypoint, distance=12):
    candidates = waypoint.next(distance)
    if len(candidates) != 1:
        raise ValueError('original Native lane has no unique forward waypoint')
    return candidates[0]


def _lane_target(native_map, ego, target_lane_id, change):
    current = native_map.get_waypoint(ego.get_transform().location)
    if current is None:
        raise ValueError('original ego waypoint missing')
    if change and current.lane_id != target_lane_id:
        for method in ('get_left_lane', 'get_right_lane'):
            neighbor = getattr(current, method)()
            if neighbor and neighbor.road_id == current.road_id and neighbor.lane_id == target_lane_id:
                return _ahead(neighbor, 15)
        raise ValueError('forward target lane unavailable during lane change')
    return _ahead(current)


class CameraCapture:
    def __init__(self, world, ego, output, carla):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        self.closed = False
        try:
            for name, width, height, pose in CAMERAS:
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x', str(width))
                blueprint.set_attribute('image_size_y', str(height))
                blueprint.set_attribute('fov', '90')
                x, y, z, pitch = pose
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch))
                # Relative mounting keeps all four cameras on the selected
                # Native route rather than leaving world-fixed cameras at (0, 0).
                sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                def receive(image, destination=frames, label=name):
                    try:
                        destination.put_nowait(image)
                    except queue.Full:
                        self.errors.append('camera queue overflow: '+label)
                sensor.listen(receive)
                self.encoders[name] = subprocess.Popen(
                    ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                     '-n', '-f', 'rawvideo', '-pixel_format', 'bgra',
                     '-video_size', f'{width}x{height}', '-framerate', '20',
                     '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra',
                     str(output/(name+'.mkv'))],
                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError('; '.join(self.errors))
        for name, _, _, _ in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError('camera/world frame mismatch: '+name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                errors.append('camera stop: '+repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    errors.append('camera encoder failed: '+name)
            except BaseException as error:
                errors.append('camera encoder '+name+': '+repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                errors.append('camera destroy: '+repr(error))
        if errors:
            raise RuntimeError('; '.join(errors))


def _spawn(world, blueprint, waypoints):
    actors = []
    try:
        for waypoint in waypoints:
            actor = world.spawn_actor(blueprint, waypoint.transform)
            if actor is None or any(existing.id == actor.id for existing in actors):
                raise ValueError('distinct Native vehicle spawn failed')
            actors.append(actor)
        return actors
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def _set_tire_friction(actors, value):
    for actor in actors:
        physics = actor.get_physics_control()
        if not physics.wheels:
            raise ValueError('Native wheel friction control unavailable')
        for wheel in physics.wheels:
            wheel.tire_friction = value
        actor.apply_physics_control(physics)


def run_native(scene, output, host, port):
    """Record only original CARLA frames on a dedicated supplied server."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields, equal

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError('Native attempt directory must already exist')
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    native_map = world.get_map()
    speed = scene['ego_target_speed_mps']
    route_points = max(120, math.ceil(
        (max(speed, scene['leader_target_speed_mps'])*scene['duration_s']+
         scene['target_body_gap_m']+20)/4)+1)
    route = discover_hill_route(native_map,
        points=route_points,
        crest_station_range_m=(max(12, 14*speed-40), 20*speed+40),
        change_station_m=scene['lane_change_start_s']*speed,
        seed_strategy=scene.get('route_seed_strategy', 'spawn'))
    waypoints = route['waypoints']
    geometry = route['geometry']
    if list(world.get_actors().filter('vehicle.*')):
        raise ValueError('dedicated Native world already contains vehicle actors')
    blueprint_library = world.get_blueprint_library()
    vehicles = list(blueprint_library.filter('vehicle.*'))
    if not vehicles:
        raise ValueError('Native motor vehicle blueprint missing')
    original_settings = world.get_settings()
    original_weather = world.get_weather()
    actors = []
    cameras = capture = frame_map = None
    errors = []
    phase = 'initializing'
    restored = False
    rows = 0
    context = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/scene['rate_hz']
        world.apply_settings(settings)
        weather = world.get_weather()
        weather.precipitation = scene['precipitation_percent']
        if 'fog_density_percent' in scene:
            weather.fog_density = scene['fog_density_percent']
        world.set_weather(weather)
        lead_index = max(3, min(len(waypoints)-4,
                                 round((scene['target_body_gap_m']+5)/4)))
        extras = scene['surrounding_vehicle_count']-1
        extra_waypoints = [route['target_waypoint']]
        while len(extra_waypoints) < extras:
            extra_waypoints.append(_ahead(extra_waypoints[-1], 20))
        spawn_points = [waypoints[0], waypoints[lead_index]]+extra_waypoints[:extras]
        actors = _spawn(world, vehicles[0], spawn_points)
        ego, leader = actors[:2]
        if 'tire_friction' in scene:
            _set_tire_friction((ego, leader), scene['tire_friction'])
        route_xy = [[p.transform.location.x, p.transform.location.y] for p in waypoints]
        context = {'case_id': scene['case_id'], 'rate_hz': scene['rate_hz'],
                   'duration_s': scene['duration_s'], 'map_source': native_map.name,
                   'route_source': route['route_source'],
                   'common_following_route_xy_m': route_xy,
                   'road_id': geometry['road_id'],
                   'following_lane_id': geometry['following_lane_id'],
                   'target_lane_id': geometry['target_lane_id'],
                   'condition_source': 'original weather and road context',
                   'hill_crest': {**geometry,
                       'source_ref': 'Native CARLA map waypoint elevation'},
                   'weather_request_percent': scene['precipitation_percent'],
                   'fog_request_percent': scene.get('fog_density_percent'),
                   'tire_friction_request': scene.get('tire_friction'),
                   'camera_profile': 'overview1080-capability'}
        _write(output/'following-context.json', context)
        _write(output/'surface_context.json', {
            'case_id': scene['case_id'], 'map_source': native_map.name,
            'road_id': geometry['road_id'],
            'following_lane_id': geometry['following_lane_id'],
            'destination_lane_id': geometry['target_lane_id'],
            'source_ref': 'original Native map and weather context'})
        _write(output/'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA live run'})
        cameras = CameraCapture(world, ego, output, carla)
        capture = PipelineCapture(client, ego, output, scene['case_id'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        start_time = world.get_snapshot().timestamp.elapsed_seconds
        phase = 'capturing'
        with ((output/'following-history.jsonl').open('x', buffering=1) as stream,
              (output/'following_samples.jsonl').open('x', buffering=1) as physical_stream):
            for index in range(round(scene['duration_s']*scene['rate_hz'])):
                t = (index+1)/scene['rate_hz']
                gap = body_gap(_body(ego), _body(leader), route_xy)
                ego_speed, leader_speed = _speed(ego), _speed(leader)
                command = speed_command(ego_speed, scene['ego_target_speed_mps'],
                                        gap, scene['target_body_gap_m'], ego_speed-leader_speed)
                lead_command = speed_command(leader_speed,
                    scene['leader_target_speed_mps'], 100, 0, 0)
                ego_target = _lane_target(native_map, ego, geometry['target_lane_id'],
                                          t >= scene['lane_change_start_s'])
                lead_target = _ahead(native_map.get_waypoint(leader.get_transform().location))
                ego.apply_control(carla.VehicleControl(
                    throttle=command['throttle'], brake=command['brake'],
                    steer=_steer(ego, ego_target)))
                leader.apply_control(carla.VehicleControl(
                    throttle=lead_command['throttle'], brake=lead_command['brake'],
                    steer=_steer(leader, lead_target)))
                for other in actors[2:]:
                    target = _ahead(native_map.get_waypoint(other.get_transform().location))
                    other.apply_control(carla.VehicleControl(
                        throttle=.2, brake=0, steer=_steer(other, target)))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise RuntimeError('original Native world frame mismatch')
                elapsed = snapshot.timestamp.elapsed_seconds-start_time
                capture.capture(frame, elapsed)
                cameras.append(frame)
                frame_map.append(frame, elapsed)
                row = sample(world, native_map, ego, leader, frame=frame,
                             relative_time_s=elapsed,
                             following_lane_id=geometry['following_lane_id'])
                stream.write(json.dumps(row, allow_nan=False)+'\n')
                physical_stream.write(json.dumps({
                    'frame': frame, 'time_s': elapsed,
                    'ego_body_vertices_m': row['ego']['body_vertices_m'],
                    'ego_lane_id': row['lane_change']['ego_lane_id']},
                    allow_nan=False)+'\n')
                rows += 1
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ['trace.jsonl', 'video_frames.jsonl',
                 'following-history.jsonl', 'following-context.json',
                 'following_samples.jsonl', 'surface_context.json',
                 'road.xodr', 'carla_recorder.log',
                 *[name+'.mkv' for name, *_ in CAMERAS]]
        _write(output/'acquisition.json', {name: {
            'kind': 'original_native',
            'sha256': hashlib.sha256((output/name).read_bytes()).hexdigest()}
            for name in names})
        phase = 'sealed'
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (capture, frame_map, cameras):
            if resource:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            world.apply_settings(original_settings)
            world.set_weather(original_weather)
            restored = (all(equal(fields(world.get_settings()).get(key), value)
                            for key, value in fields(original_settings).items()) and
                        abs(world.get_weather().precipitation-original_weather.precipitation) < 1e-6 and
                        abs(world.get_weather().fog_density-original_weather.fog_density) < 1e-6)
        except BaseException as error:
            errors.append(repr(error))
        if phase == 'sealed' and not errors and restored:
            seal_capture(output, frames=rows,
                restoration={'restored': True,
                             'settings_readback': 'synchronous mode, fixed delta and precipitation restored'},
                errors=[], encoder_exit_codes={name: 0 for name, *_ in CAMERAS},
                context={'following_hill_crest': context})
        else:
            _write(output/'native-run-status.json', {
                'phase': phase, 'errors': errors, 'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')


def _body(actor):
    return [[point.x, point.y, point.z]
            for point in actor.bounding_box.get_world_vertices(actor.get_transform())]
