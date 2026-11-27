"""Original 20 Hz, four-camera roadside-signal approach acquisition.

CARLA is imported only by run_native. Every source claim remains subject to
independent original review; this module does not assign a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from signal_approach import measure_original, sha


CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n',
                          encoding='utf-8')


def speed(actor):
    value = actor.get_velocity()
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


def vertices(actor):
    return [[float(v.x), float(v.y)] for v in
            actor.bounding_box.get_world_vertices(actor.get_transform())]


def steer_to(actor, target):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(target[1] - pose.location.y,
                                      target[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


def control_to(actor, target, halt, throttle, braking_factor):
    position = actor.get_location()
    distance = math.dist((position.x, position.y), target)
    velocity = speed(actor)
    if halt and distance <= 1.25:
        return {'throttle': 0.0, 'brake': 1.0,
                'hand_brake': velocity <= 0.1, 'steer': 0.0}
    braking = halt and distance <= velocity * velocity / braking_factor + 1.5
    return {'throttle': 0.0 if braking else throttle,
            'brake': 0.65 if braking else 0.0,
            'hand_brake': False, 'steer': steer_to(actor, target)}


class FourCameras:
    def __init__(self, world, carla, ego, signal_xy, output):
        self.sensors, self.encoders, self.buffers, self.errors = [], {}, {}, []
        poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                 (2, -9, 9, -35), (0, 0, 2, 0))
        try:
            for (name, width, height), (dx, dy, z, pitch) in zip(CAMERAS, poses):
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x', str(width))
                blueprint.set_attribute('image_size_y', str(height))
                blueprint.set_attribute('fov', '90')
                attached = name == 'driver_reference'
                location = carla.Location(x=dx, y=dy, z=z) if attached else carla.Location(
                    x=signal_xy[0] + dx, y=signal_xy[1] + dy, z=z)
                sensor = world.spawn_actor(blueprint,
                                           carla.Transform(location, carla.Rotation(pitch=pitch)),
                                           attach_to=ego if attached else None)
                self.sensors.append(sensor)
                self.buffers[name] = queue.Queue(maxsize=4)

                def receive(image, buffer=self.buffers[name], label=name):
                    try:
                        buffer.put_nowait(image)
                    except queue.Full:
                        self.errors.append('camera queue overflow: ' + label)

                sensor.listen(receive)
                command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-n', '-f', 'rawvideo', '-pixel_format', 'bgra',
                           '-video_size', f'{width}x{height}', '-framerate', '20',
                           '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra',
                           str(output / (name + '.mkv'))]
                self.encoders[name] = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError('; '.join(self.errors))
        for name, _, _ in CAMERAS:
            image = self.buffers[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError('camera frame differs from world frame: ' + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        failures = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                failures.append(repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    failures.append('camera encoder failed: ' + name)
            except BaseException as error:
                failures.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                failures.append(repr(error))
        self.sensors, self.encoders = [], {}
        if failures:
            raise RuntimeError('; '.join(failures))


def spawn_vehicle(world, carla, blueprint_id, xy, owned):
    location = carla.Location(x=xy[0], y=xy[1], z=0)
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None:
        raise ValueError('reviewed signal route lacks live waypoint')
    location.z = waypoint.transform.location.z + 0.5
    blueprint = world.get_blueprint_library().find(blueprint_id)
    actor = world.try_spawn_actor(blueprint, carla.Transform(
        location, waypoint.transform.rotation))
    if actor is None or actor.type_id != blueprint_id:
        raise ValueError('motor vehicle spawn/readback failed')
    owned.append(actor)
    return actor


def read_signal(world, scene):
    actor = world.get_actors().find(int(scene['signal_actor_id']))
    if actor is None or not actor.type_id.startswith(('traffic.traffic_light', 'static.')):
        raise ValueError('reviewed roadside signal actor missing')
    if (scene['signal_official_status'] == 'official' and
            not actor.type_id.startswith('traffic.traffic_light')):
        raise ValueError('official signal must be a live traffic light actor')
    pose = actor.get_transform().location
    if math.dist((pose.x, pose.y), scene['signal_xy']) > 1.0:
        raise ValueError('live roadside signal placement differs')
    return actor


def run_native(config, packet, case, geometry, packet_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError('materialized Native attempt directory required')
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    scene = packet['scene']
    owned, rows, errors = [], [], []
    cameras = capture = frame_map = None
    phase, restored = 'initializing', False
    try:
        archive = output / 'reviewed-signal-packet'
        archive.mkdir(exist_ok=False)
        shutil.copy2(packet_path, archive / 'site.json')
        for source in packet['sources'].values():
            source_path = (packet_path.parent / source['path']).resolve()
            target = archive / source['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
        map_record = json.loads((packet_path.parent /
                                 packet['sources']['map']['path']).read_text())
        if (world.get_map().name != packet['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() !=
                map_record['opendrive_sha256']):
            raise ValueError('reviewed signal highway map differs from Native world')
        signal = read_signal(world, scene)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        ego = spawn_vehicle(world, carla, scene['ego_blueprint'],
                            scene['incoming_route_xy'][0], owned)
        if abs(float(ego.bounding_box.extent.x) - scene['body_front_offset_m']) > 0.1:
            raise ValueError('live vehicle front offset differs from reviewed target')
        forward = ego.get_transform().get_forward_vector()
        if forward.x * geometry['heading_xy'][0] + forward.y * geometry['heading_xy'][1] < 0.95:
            raise ValueError('live ego lane points away from reviewed signal approach')
        traffic_route = scene['conflict_actor_route_xy'] if case.exception == 'traffic_conflict' else scene['traffic_route_xy']
        traffic = spawn_vehicle(world, carla, scene['traffic_actor_blueprint'],
                                traffic_route[0], owned)
        write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA 20 Hz four-view roadside-signal capture',
            'reviewed_packet_sha256': sha(packet_path),
            'physical_acceptance_claimed': False})
        cameras = FourCameras(world, carla, ego, scene['signal_xy'], output)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        phase = 'capturing'
        with (output / 'signal-history.jsonl').open('x', buffering=1) as stream:
            for _ in range(config['duration_s'] * config['rate_hz']):
                ego_control = control_to(ego, scene['halt_target_xy'], True,
                                         config['engineering_throttle'],
                                         config['engineering_braking_factor'])
                traffic_control = control_to(traffic, traffic_route[-1], False, 0.20, 5.0)
                ego.apply_control(carla.VehicleControl(**ego_control))
                traffic.apply_control(carla.VehicleControl(**traffic_control))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('original world frame readback changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                row = {
                    'original_frame': frame, 'time_s': time_s,
                    'original_source': True,
                    'ego_actor_id': str(ego.id), 'traffic_actor_id': str(traffic.id),
                    'signal_id': scene['signal_id'],
                    'signal_actor_id': str(signal.id),
                    'signal_indication': str(signal.get_state()) if hasattr(signal, 'get_state') else 'unavailable',
                    'body_vertices_xy_m': vertices(ego),
                    'ego_speed_mps': speed(ego), 'traffic_speed_mps': speed(traffic),
                    'ego_control': ego_control,
                    'activity': case.activity, 'exception': case.exception,
                    'signal_source_sha256': scene['signal_source_sha256'],
                    'highway_source_sha256': scene['highway_source_sha256'],
                    'authority_source_sha256': scene['authority_source_sha256'],
                    'traffic_source_sha256': scene['traffic_source_sha256'],
                    'frame_source_sha256': sha(__file__)}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / 'signal-site.json', packet)
        write(output / 'signal-geometry.json', geometry)
        write(output / 'signal-measurement.json', measure_original(rows, scene, case))
        names = ['trace.jsonl', 'video_frames.jsonl', 'signal-history.jsonl',
                 'signal-site.json', 'signal-geometry.json', 'signal-measurement.json',
                 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name, _, _ in CAMERAS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob('*') if path.is_file())
        write(output / 'acquisition.json', {
            name: {'kind': 'original_native', 'sha256': sha(output / name)} for name in names})
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
        for actor in reversed(owned):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            restored = restore(client, saved_world)['restored']
        except BaseException as error:
            errors.append(repr(error))
        if phase == 'sealed' and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={'restored': True,
                                      'settings_readback': 'original world snapshot restored'},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in CAMERAS},
                         context={'roadside_signal_case': config['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {'phase': phase,
                                                      'errors': errors,
                                                      'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
