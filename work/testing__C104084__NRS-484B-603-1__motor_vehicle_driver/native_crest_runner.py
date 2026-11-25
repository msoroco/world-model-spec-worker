"""Original Native acquisition for the three selected crest speed profiles.

The runner is deliberately lazy with respect to CARLA. A local operator supplies
the CARLA module/client and a reviewed prescribed-limit source. Saved audits,
not this runner, decide whether a completed capture is usable.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile

from crest_controller import step
from native_crest_capture import NativeTickRecorder
from native_crest_setup import load_and_bind
from saved_crest_audit import ASSIGNMENT, CAMERAS, FRAME_COUNT, PROFILES
from saved_crest_bundle import assemble

DIMENSIONS = {'front': (1920, 1080), 'left': (1280, 720),
              'right': (1280, 720), 'rear': (1280, 720)}
CAMERA_POSES = {'front': (0, 0), 'left': (-90, 0),
                'right': (90, 0), 'rear': (180, 0)}


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _distance_clearance(ego, other):
    a, b = ego.get_transform().location, other.get_transform().location
    center = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
    ea, eb = ego.bounding_box.extent, other.bounding_box.extent
    return max(0.0, center - math.hypot(ea.x, ea.y) - math.hypot(eb.x, eb.y))


class FFV1Encoder:
    """Stream each original BGRA camera image to a lossless Matroska file."""

    def __init__(self, path, width, height):
        self.width, self.height = width, height
        self.path = Path(path)
        self.process = subprocess.Popen(
            ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
             '-video_size', f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0',
             '-an', '-c:v', 'ffv1', '-level', '3', str(self.path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.count = 0

    def append(self, image):
        if (image.width, image.height) != (self.width, self.height):
            raise ValueError('original camera dimensions differ')
        raw = bytes(image.raw_data)
        if len(raw) != self.width * self.height * 4:
            raise ValueError('original BGRA camera bytes differ')
        self.process.stdin.write(raw)
        self.count += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        error = self.process.stderr.read().decode('utf-8', errors='replace')
        code = self.process.wait()
        self.process.stderr.close()
        if code or self.count != FRAME_COUNT:
            raise ValueError(f'lossless camera encoding incomplete: {code}, {self.count}, {error[-500:]}')
        return {'path': str(self.path), 'sha256': _sha(self.path),
                'frame_count': self.count, 'dimensions': [self.width, self.height]}

    def abort(self):
        if self.process.poll() is None:
            self.process.kill()
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.wait()
        self.process.stderr.close()


def _spawn(world, blueprint, transform):
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError('original Native actor spawn failed')
    return actor


def capture(client, carla, *, map_path, map_sha256, case_id, destination,
            limit_mps, limit_source_ref, capture_ref, scratch_root,
            encoder_factory=FFV1Encoder):
    """Capture one complete original Native attempt and seal it after audits.

    The caller must supply a reviewed prescribed limit and its source reference.
    The authored map alone does not establish an externally posted speed limit.
    No expected speed profile is substituted for observed speed.
    """
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('exact selected crest case required')
    profile = case_id[len(ASSIGNMENT) + 2:]
    if profile not in PROFILES:
        raise ValueError('exact selected crest profile required')
    if (type(limit_mps) not in (int, float) or not math.isfinite(limit_mps)
            or limit_mps <= 12 or not isinstance(limit_source_ref, str)
            or not limit_source_ref.strip()):
        raise ValueError('reviewed above-approach prescribed limit source required')
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch_root = Path(scratch_root).resolve()
    if '.runtime-work' not in scratch_root.parts:
        raise ValueError('capture scratch must be under .runtime-work')
    scratch_root.mkdir(parents=True, exist_ok=True)
    source_dir = Path(tempfile.mkdtemp(prefix='crest-native-', dir=scratch_root))
    actors, encoders = [], {}
    world = None
    original_settings = None
    try:
        bound = load_and_bind(client, map_path, expected_file_sha256=map_sha256)
        world = bound['world']
        original_settings = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        native_map = world.get_map()
        (source_dir / 'native-map.xodr').write_text(native_map.to_opendrive(), encoding='utf-8')
        forward = bound['routes']['forward']['waypoints']
        opposite = bound['routes']['opposing']['waypoints']
        _write_json(source_dir / 'grade.json', forward)
        _write_json(source_dir / 'other-route.json', [
            {'road_id': 603, 'lane_id': 1, 's_m': p['s_m'],
             'source_ref': p['source_ref']} for p in reversed(opposite)])
        grade_sha = _sha(source_dir / 'grade.json')
        blueprint_library = world.get_blueprint_library()
        vehicle_blueprint = blueprint_library.find('vehicle.tesla.model3')
        ego_wp = native_map.get_waypoint_xodr(603, -1, 230.0)
        other_wp = native_map.get_waypoint_xodr(603, 1, 270.0)
        if ego_wp is None or other_wp is None:
            raise ValueError('surveyed original spawn waypoints unavailable')
        ego = _spawn(world, vehicle_blueprint, ego_wp.transform)
        actors.append(ego)
        other = _spawn(world, vehicle_blueprint, other_wp.transform)
        actors.append(other)
        other.apply_control(carla.VehicleControl(throttle=0, brake=1))
        camera_queues = {}
        for name in CAMERAS:
            width, height = DIMENSIONS[name]
            blueprint = blueprint_library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', '90')
            blueprint.set_attribute('sensor_tick', '0.05')
            yaw, pitch = CAMERA_POSES[name]
            pose = carla.Transform(carla.Location(x=0, y=0, z=2.4),
                                   carla.Rotation(yaw=yaw, pitch=pitch))
            camera = world.spawn_actor(blueprint, pose, attach_to=ego)
            actors.append(camera)
            inbox = queue.Queue(maxsize=4)
            camera.listen(inbox.put)
            camera_queues[name] = inbox
            encoders[name] = encoder_factory(source_dir / f'{name}.mkv', width, height)
        _write_json(source_dir / 'context.json', {
            'map_grade_sha256': grade_sha, 'road_id': 603,
            'highway_status': 'source_observed_road',
            'highway_source_ref': f'native-map:{bound["native_map_sha256"]}',
            'prescribed_limit_mps': limit_mps,
            'limit_source_ref': limit_source_ref,
            'ego_actor_id': str(ego.id), 'other_actor_id': str(other.id),
            'lawful_entry_review': 'unresolved', 'due_care_review': 'unresolved'})
        recorder = NativeTickRecorder(ego_actor_id=str(ego.id),
            other_actor_id=str(other.id), native_capture_ref=capture_ref)
        crest = bound['routes']['forward']['crest_station_m']
        for index in range(FRAME_COUNT):
            frame = world.tick()
            images = {name: camera_queues[name].get(timeout=10) for name in CAMERAS}
            if any(image.frame != frame for image in images.values()):
                raise ValueError('original camera world-frame join differs')
            waypoint = native_map.get_waypoint(ego.get_transform().location,
                                               project_to_road=True,
                                               lane_type=carla.LaneType.Driving)
            other_waypoint = native_map.get_waypoint(other.get_transform().location,
                project_to_road=True, lane_type=carla.LaneType.Driving)
            if (waypoint.road_id, waypoint.lane_id) != (603, -1) or (
                    other_waypoint.road_id, other_waypoint.lane_id) != (603, 1):
                raise ValueError('original vehicles left surveyed driving lanes')
            velocity = ego.get_velocity()
            speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
            station = waypoint.s - 230.0
            other_station = other_waypoint.s - 230.0
            recorder.append(world_frame=frame,
                ego={'actor_id': str(ego.id), 'station_m': station,
                     'speed_mps': speed, 'body_clearance_m': _distance_clearance(ego, other),
                     'source_ref': f'{capture_ref}:ego:{frame}'},
                other={'actor_id': str(other.id), 'station_m': other_station,
                       'source_ref': f'{capture_ref}:other:{frame}'},
                camera_frames=images)
            for name in CAMERAS:
                encoders[name].append(images[name])
            step(ego, carla.VehicleControl, profile, crest_s_m=crest,
                 ego_s_m=station, measured_speed_mps=speed,
                 route_end_s_m=270.0)
        recorder.write(source_dir)
        for encoder in encoders.values():
            encoder.close()
        encoders.clear()
        spec = {'profile': profile, 'acquisition_kind': 'original_native',
                'native_map_sha256': bound['native_map_sha256'],
                'native_capture_ref': capture_ref, 'approach_start_m': 0.0,
                'camera_dimensions': {name: list(DIMENSIONS[name]) for name in CAMERAS},
                'sources': {key: str(source_dir / filename) for key, filename in {
                    'native_map_source': 'native-map.xodr', 'grade_source': 'grade.json',
                    'motion_source': 'motion.json', 'context_source': 'context.json',
                    'other_route_source': 'other-route.json',
                    'frame_map_source': 'frame-map.jsonl'}.items()},
                'cameras': {name: str(source_dir / f'{name}.mkv') for name in CAMERAS}}
        return assemble(spec, destination, expected_case=case_id)
    finally:
        for encoder in encoders.values():
            encoder.abort()
        for actor in reversed(actors):
            try:
                actor.stop() if hasattr(actor, 'stop') else None
                actor.destroy()
            except Exception:
                pass
        if world is not None and original_settings is not None:
            world.apply_settings(original_settings)
        shutil.rmtree(source_dir)
