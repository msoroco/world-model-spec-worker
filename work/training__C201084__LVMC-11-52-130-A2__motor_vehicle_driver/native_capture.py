"""Original four-camera acquisition for C201084 fire-lane stop attempts.

No success flag is set from attempted control. Saved source measurements and
independent pixel/Fire Code review determine what the run actually showed.
"""
import copy
import json
import queue
import subprocess
from math import hypot, isfinite
from pathlib import Path

from fire_lane_survey import CAMERAS, require
from native_controller import apply


CAMERA_SPECS = (
    ('overview', 640, 360, (-8, 0, 12), 0, -55),
    ('approach', 640, 360, (3, 0, 2), 0, -8),
    ('reference_corner', 1280, 720, (0, 3, 2), 90, -8),
    ('driver_reference', 1280, 720, (1, 0, 1.6), 0, -4),
)
assert tuple(row[0] for row in CAMERA_SPECS) == CAMERAS


class FFV1Sink:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.width, self.height = width, height
        self.stderr = self.path.with_suffix('.ffmpeg.log').open('xb')
        self.process = subprocess.Popen([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size',
            f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0',
            '-an', '-c:v', 'ffv1', '-threads', '1', str(path)],
            stdin=subprocess.PIPE, stderr=self.stderr)
        self.count = 0

    def write(self, image):
        raw = bytes(image.raw_data)
        require(len(raw) == self.width*self.height*4,
                'Original camera pixel dimensions differ')
        self.process.stdin.write(raw)
        self.count += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=180)
        self.stderr.close()
        require(code == 0, 'Original camera FFV1 encoder failed')


def install_cameras(world, carla, ego, callback):
    library = world.get_blueprint_library()
    sensors = []
    try:
        for name, width, height, xyz, yaw, pitch in CAMERA_SPECS:
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', '90')
            transform = carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                        carla.Rotation(yaw=yaw, pitch=pitch))
            sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
            require(sensor is not None, 'Original camera spawn failed: '+name)
            sensors.append(sensor)
            sensor.listen(lambda image, camera=name: callback(camera, image))
    except Exception:
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()
        raise
    return sensors


def sample_native(world, carla, ego, follower, sign, plan):
    transform = ego.get_transform()
    location = transform.location
    waypoint = world.get_map().get_waypoint(location, project_to_road=True,
                                            lane_type=carla.LaneType.Driving)
    require(waypoint is not None and
            waypoint.road_id == plan['fixed_context']['road_id'],
            'Original ego departed surveyed road')
    sign_location = sign.get_transform().location
    surveyed = plan['survey_geometry']['posted_sign_xy_m']
    require(sign.id == plan['fixed_context']['posted_sign_actor_id'] and
            hypot(sign_location.x-surveyed[0], sign_location.y-surveyed[1]) <= 0.5,
            'Original sign actor identity/location changed')
    vertices = ego.bounding_box.get_world_vertices(transform)
    require(len(vertices) >= 4, 'Original ego body vertices unavailable')
    velocity = ego.get_velocity()
    other_transform = follower.get_transform()
    other_location = other_transform.location
    other_waypoint = world.get_map().get_waypoint(
        other_location, project_to_road=True, lane_type=carla.LaneType.Driving)
    require(other_waypoint is not None and
            other_waypoint.road_id == plan['fixed_context']['road_id'],
            'Original following vehicle departed surveyed road')
    other_velocity = follower.get_velocity()
    other_vertices = follower.bounding_box.get_world_vertices(other_transform)
    require(len(other_vertices) >= 4,
            'Original following vehicle body unavailable')
    return {'source_kind': 'original_carla_actor_and_map_readback',
            'ego_actor_id': ego.id, 'driving_road_id': waypoint.road_id,
            'driving_lane_id': waypoint.lane_id, 'sign_actor_id': sign.id,
            'sign_position_xyz_m': [sign_location.x, sign_location.y, sign_location.z],
            'ego_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'ego_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in vertices],
            'ego_pose_xyz_m': [location.x, location.y, location.z],
            'ego_yaw_deg': transform.rotation.yaw,
            'following_actor_id': follower.id,
            'following_road_id': other_waypoint.road_id,
            'following_velocity_xyz_mps': [other_velocity.x,
                                           other_velocity.y, other_velocity.z],
            'following_body_vertices_xyz_m': [[v.x, v.y, v.z]
                                              for v in other_vertices],
            'following_pose_xyz_m': [other_location.x,
                                    other_location.y, other_location.z],
            'following_gap_m': hypot(location.x-other_location.x,
                                     location.y-other_location.y)}


class OriginalFrameMap:
    """Retain camera/world identities in acquisition order inside the bundle."""

    def __init__(self, path):
        self.stream = Path(path).open('x', encoding='utf-8', buffering=1)
        self.index = 0
        self.previous = None

    def append(self, frame, time_s):
        require(type(frame) is int and frame >= 0 and
                type(time_s) in (int, float) and isfinite(time_s),
                'Invalid original frame identity')
        if self.previous is not None:
            require(frame > self.previous[0] and time_s > self.previous[1],
                    'Original frames and times must increase')
        row = {'video_frame': self.index, 'carla_frame': frame,
               'native_frame': frame, 'time_s': time_s}
        self.stream.write(json.dumps(row, allow_nan=False)+'\n')
        self.previous = (frame, time_s)
        self.index += 1
        return row

    def close(self):
        self.stream.close()


def acquire(world, carla, ego, follower, sign, plan, case, attempt,
            *, sink_factory=FFV1Sink, camera_installer=install_cameras,
            timeout_s=10, frame_map_factory=OriginalFrameMap):
    require(case in ('reference', 'contrast'), 'Unknown fire-lane case')
    require(plan['capture_hz'] == 20 and plan['capture_frames'] >= 600 and
            plan['camera_names'] == list(CAMERAS),
            'Original capture contract differs')
    settings = world.get_settings()
    require(settings.synchronous_mode and settings.fixed_delta_seconds == 0.05,
            'Original world must be synchronous at 20 Hz')
    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    originals = ('native-actors.jsonl', 'video_frames.jsonl',
                 *(name+'.mkv' for name in CAMERAS))
    require(not any((attempt/name).exists() for name in originals),
            'Retain prior originals; use a fresh attempt')
    queues = {name: queue.Queue() for name in CAMERAS}
    sensors = []
    sinks = {}
    frames = None
    rows = None
    first_elapsed = None
    previous_frame = -1
    try:
        sensors = camera_installer(world, carla, ego,
                                   lambda name, image: queues[name].put(image))
        for name, width, height, *_ in CAMERA_SPECS:
            sinks[name] = sink_factory(attempt/(name+'.mkv'), width, height)
        frames = frame_map_factory(attempt/'video_frames.jsonl')
        rows = (attempt/'native-actors.jsonl').open('x', encoding='utf-8')
        target = plan['cases'][case]['stop_center_xy_m']
        tuning = plan.get('controller_tuning') or {}
        stop_tuning = {key: tuning[key] for key in
                       ('stop_radius_m', 'cruise_mps', 'deceleration_mps2')
                       if key in tuning}
        following_brake_gap_m = tuning.get('following_brake_gap_m', 7.0)
        following_cruise_throttle = tuning.get('following_cruise_throttle', 0.32)
        for index in range(plan['capture_frames']):
            requested = apply(ego, carla, target, **stop_tuning)
            ego_location = ego.get_transform().location
            following_location = follower.get_transform().location
            gap = hypot(ego_location.x-following_location.x,
                        ego_location.y-following_location.y)
            follower.apply_control(carla.VehicleControl(
                throttle=0.0 if gap < following_brake_gap_m else following_cruise_throttle,
                brake=1.0 if gap < following_brake_gap_m else 0.0,
                steer=0.0, hand_brake=False))
            native_frame = world.tick()
            require(type(native_frame) is int and native_frame > previous_frame,
                    'Original CARLA world frame did not advance')
            previous_frame = native_frame
            for name in CAMERAS:
                image = queues[name].get(timeout=timeout_s)
                require(image.frame == native_frame,
                        'Original camera frame join differs: '+name)
                sinks[name].write(image)
            elapsed = world.get_snapshot().timestamp.elapsed_seconds
            if first_elapsed is None:
                first_elapsed = elapsed
            frames.append(native_frame, elapsed-first_elapsed)
            observed = sample_native(world, carla, ego, follower, sign, plan)
            observed.update(frame=native_frame, video_frame=index,
                            requested_control=requested)
            rows.write(json.dumps(observed, allow_nan=False)+'\n')
    finally:
        if rows is not None:
            rows.close()
        if frames is not None:
            frames.close()
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()
        errors = []
        for sink in sinks.values():
            try:
                sink.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]
    return {'source_frames': plan['capture_frames'],
            'camera_paths': [name+'.mkv' for name in CAMERAS],
            'frame_map': 'video_frames.jsonl', 'actors': 'native-actors.jsonl',
            'physical_completion_claimed': False}


def acquire_with_world_restore(world, *args, **kwargs):
    previous = world.get_settings()
    configured = copy.copy(previous)
    configured.synchronous_mode = True
    configured.fixed_delta_seconds = 0.05
    world.apply_settings(configured)
    try:
        result = acquire(world, *args, **kwargs)
    finally:
        world.apply_settings(previous)
    restored = world.get_settings()
    require(restored.synchronous_mode == previous.synchronous_mode and
            restored.fixed_delta_seconds == previous.fixed_delta_seconds,
            'Original world timing was not restored')
    result['restoration_verified'] = True
    return result
