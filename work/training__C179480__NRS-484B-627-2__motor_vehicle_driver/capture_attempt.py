"""CPU-testable CARLA acquisition for C179480; finalization is separate.

This owns only actors/sensors it creates and original source capture. It does
not emit a Native result or infer that an attempted stop physically succeeded.
"""
import copy
import json
import queue
import subprocess
from pathlib import Path
from math import cos, hypot, radians, sin

from native_controller import StopControl, apply_stop_control, camera_specs, install_cameras


def sample_native(world, carla, ego, follower):
    """Read original actor motion and lane geometry at the current world tick."""
    mapping = world.get_map()
    ego_transform = ego.get_transform()
    ego_position = ego_transform.location
    drive_lane = mapping.get_waypoint(ego_position, project_to_road=True,
                                      lane_type=carla.LaneType.Driving)
    if drive_lane is None or drive_lane.lane_width <= 0:
        raise ValueError('No surveyed driving lane near the stop')
    center = drive_lane.transform.location
    yaw = radians(drive_lane.transform.rotation.yaw)
    right = (-sin(yaw), cos(yaw))
    def lateral(point):
        return ((point.x-center.x)*right[0] + (point.y-center.y)*right[1])
    vertices = ego.bounding_box.get_world_vertices(ego_transform)
    if len(vertices) < 4:
        raise ValueError('Missing original ego body footprint')
    offsets = [lateral(vertex) for vertex in vertices]
    half_lane = drive_lane.lane_width / 2
    overlap = min(offsets) <= half_lane and max(offsets) >= -half_lane
    center_lane = mapping.get_waypoint(ego_position, project_to_road=False,
                                       lane_type=carla.LaneType.Driving)
    follower_position = follower.get_transform().location
    def speed(actor):
        v = actor.get_velocity()
        return hypot(hypot(v.x, v.y), v.z)
    return {
        'ego_speed_mps': speed(ego),
        'ego_on_roadway': center_lane is not None,
        'ego_lane_overlap': overlap,
        'ego_body_lateral_min_m': min(offsets),
        'ego_body_lateral_max_m': max(offsets),
        'driving_lane_width_m': drive_lane.lane_width,
        'driving_road_id': drive_lane.road_id,
        'driving_lane_id': drive_lane.lane_id,
        'ego_x_m': ego_position.x, 'ego_y_m': ego_position.y,
        'following_x_m': follower_position.x,
        'following_y_m': follower_position.y,
        'following_speed_mps': speed(follower),
        'following_gap_m': hypot(ego_position.x-follower_position.x,
                                 ego_position.y-follower_position.y),
        'source_kind': 'original_carla_actor_and_map_readback',
    }


class FFV1Sink:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.error = self.path.with_suffix('.ffmpeg.log')
        self.error_stream = self.error.open('xb')
        self.process = subprocess.Popen([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size',
            f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0',
            '-an', '-c:v', 'ffv1', '-threads', '1', str(self.path)],
            stdin=subprocess.PIPE, stderr=self.error_stream)
        self.frame_size = width * height * 4
        self.count = 0

    def write(self, image):
        data = bytes(image.raw_data)
        if len(data) != self.frame_size:
            raise ValueError('Source camera frame has wrong pixel count')
        self.process.stdin.write(data)
        self.count += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=60)
        self.error_stream.close()
        if code:
            raise ValueError('Source camera FFV1 encoding failed: ' + str(self.error))


def _frame_map(path):
    # Import the pinned original-frame writer without copying its semantics.
    import sys
    repo = Path(__file__).resolve().parents[2]
    runtime = str(repo / 'runtime/pipeline')
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    from scenario_pipeline.worker_exchange.native_output import FrameMap
    return FrameMap(path)


def acquire(world, carla, ego, follower, blueprints, stop_xy, attempt,
            *, frames, sample, sink_factory=FFV1Sink, timeout_s=10):
    """Drive, tick and retain exact synchronized original actor/video sources.

    `sample` must read the current world and return the source fields expected
    by source_measurement. The Native runner must provide a map/footprint based
    implementation; this function never substitutes planned geometry as data.
    """
    if type(frames) is not int or frames < 2:
        raise ValueError('Capture needs at least two 20 Hz frames')
    settings = world.get_settings()
    if not settings.synchronous_mode or settings.fixed_delta_seconds != 0.05:
        raise ValueError('Capture requires original synchronous 20 Hz world')
    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=False)
    queues = {item['name']: queue.Queue() for item in camera_specs()}
    sensors = []
    sinks = {}
    frame_map = None
    rows = None
    prior_frame = -1
    controller = StopControl(*stop_xy)
    try:
        sensors = install_cameras(world, blueprints, carla, ego,
                                  lambda name, image: queues[name].put(image))
        for item in camera_specs():
            sinks[item['name']] = sink_factory(
                attempt / (item['name'] + '.mkv'), item['width'], item['height'])
        frame_map = _frame_map(attempt / 'video_frames.jsonl')
        rows = (attempt / 'native-actors.jsonl').open('x', encoding='utf-8')
        for index in range(frames):
            command = apply_stop_control(ego, carla.VehicleControl, controller)
            # A following actor approaches in the same surveyed lane. Its actual
            # response is retained as source data, never assumed from this command.
            ego_xy = ego.get_transform().location
            other_xy = follower.get_transform().location
            gap = ((ego_xy.x-other_xy.x)**2 + (ego_xy.y-other_xy.y)**2)**0.5
            follower.apply_control(carla.VehicleControl(
                throttle=0.0 if gap < 7.0 else 0.32,
                brake=1.0 if gap < 7.0 else 0.0, steer=0.0))
            native_frame = world.tick()
            if type(native_frame) is not int or native_frame <= prior_frame:
                raise ValueError('Native world frame did not advance')
            prior_frame = native_frame
            for item in camera_specs():
                name = item['name']
                image = queues[name].get(timeout=timeout_s)
                if image.frame != native_frame:
                    raise ValueError('Source camera frame join differs: ' + name)
                sinks[name].write(image)
            timestamp = world.get_snapshot().timestamp.elapsed_seconds
            frame_map.append(native_frame, timestamp)
            observed = sample(world, ego, follower)
            if not isinstance(observed, dict) or 'frame' in observed:
                raise ValueError('Native sample must provide unsealed source fields')
            record = dict(observed, frame=native_frame,
                          ego_command=command['command'], video_frame=index)
            rows.write(json.dumps(record, allow_nan=False) + '\n')
    finally:
        if rows is not None:
            rows.close()
        if frame_map is not None:
            frame_map.close()
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()
        close_errors = []
        for sink in sinks.values():
            try:
                sink.close()
            except Exception as error:
                close_errors.append(error)
        if close_errors:
            raise close_errors[0]
    return {'source_frames': frames,
            'camera_paths': [item['name']+'.mkv' for item in camera_specs()],
            'frame_map': 'video_frames.jsonl', 'actors': 'native-actors.jsonl',
            'physical_completion_claimed': False}


def acquire_with_world_restore(world, *args, **kwargs):
    """Temporarily configure synchronous 20 Hz capture and restore settings."""
    original = world.get_settings()
    configured = copy.copy(original)
    configured.synchronous_mode = True
    configured.fixed_delta_seconds = 0.05
    world.apply_settings(configured)
    try:
        return acquire(world, *args, **kwargs)
    finally:
        world.apply_settings(original)
