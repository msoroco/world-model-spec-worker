"""Original 20 Hz highway-side parking and four-view acquisition."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from parking import construct, measure_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def speed(actor):
    value = actor.get_velocity()
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


def body_rect(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [min(p.x for p in points), min(p.y for p in points),
            max(p.x for p in points), max(p.y for p in points)]


def steer_to(actor, xy):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(xy[1] - pose.location.y,
                                      xy[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


class Cameras:
    SPECS = (('overview', 1920, 1080), ('approach', 1280, 720),
             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))

    def __init__(self, world, carla, ego, center_xy, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                 (2, -9, 9, -35), (0, 0, 2, 0))
        try:
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x', str(width))
                blueprint.set_attribute('image_size_y', str(height))
                blueprint.set_attribute('fov', '90')
                attached = name == 'driver_reference'
                point = carla.Location(x=dx, y=dy, z=z) if attached else carla.Location(
                    x=center_xy[0] + dx, y=center_xy[1] + dy, z=z)
                pose = carla.Transform(point, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(blueprint, pose, attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, buffer=frames, label=name):
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
                self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError('; '.join(self.errors))
        for name, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
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
        self.sensors = []
        self.encoders = {}
        if failures:
            raise RuntimeError('; '.join(failures))


class Adapter:
    """Review-gated two-vehicle construction matching parking.construct."""

    def __init__(self, world, carla, packet):
        self.world, self.carla, self.packet = world, carla, packet
        self.owned = []
        self.edge = self.ego = None
        self.route = self.target = self.activity = None

    def spawn_vehicle(self, xy, role):
        if role not in ('ego', 'edge_vehicle'):
            raise ValueError('unknown parking vehicle role')
        location = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed highway location lacks waypoint')
        location.z = waypoint.transform.location.z + 0.5
        blueprint_id = self.packet['ego_blueprint_id' if role == 'ego' else 'edge_blueprint_id']
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint, self.carla.Transform(
            location, waypoint.transform.rotation))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError('reviewed motor-vehicle spawn/readback failed: ' + role)
        self.owned.append(actor)
        if role == 'ego':
            self.ego = actor
        else:
            self.edge = actor
        return actor

    def hold_vehicle(self, vehicle, activity):
        if vehicle is not self.edge or activity != 'park':
            raise ValueError('edge vehicle must be parked')
        vehicle.apply_control(self.carla.VehicleControl(brake=1.0, hand_brake=True))

    def set_route(self, vehicle, route, target_xy):
        if vehicle is not self.ego or len(route) < 2:
            raise ValueError('ego parking route invalid')
        self.route = tuple(tuple(point) for point in route)
        self.target = tuple(target_xy)

    def request_halt(self, vehicle, target_xy, activity):
        if (vehicle is not self.ego or tuple(target_xy) != self.target or
                activity not in ('stop', 'stand', 'park')):
            raise ValueError('parking halt request invalid')
        self.activity = activity

    def destroy(self, actor):
        actor.destroy()
        self.owned.remove(actor)


def control_to(actor, target, throttle, braking_factor):
    position = actor.get_location()
    distance = math.dist((position.x, position.y), target)
    current_speed = speed(actor)
    if distance <= 1.25:
        return {'throttle': 0.0, 'brake': 1.0,
                'hand_brake': current_speed <= 0.1, 'steer': 0.0}
    braking = distance <= current_speed * current_speed / braking_factor + 1.5
    return {'throttle': 0.0 if braking else throttle,
            'brake': 0.65 if braking else 0.0, 'hand_brake': False,
            'steer': steer_to(actor, target)}


def run_native(config, packet, case, packet_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError('Native attempt directory must already exist')
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    adapter = cameras = capture = frame_map = None
    rows, errors, phase, restored = [], [], 'initializing', False
    try:
        archive = output / 'reviewed-site-packet'
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
            raise ValueError('reviewed parking map differs from Native world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        adapter = Adapter(world, carla, packet)
        site = packet['site']
        built = construct(adapter, site, case)
        ego, edge = adapter.ego, adapter.edge
        if ego is None or edge is None or len(built['owned']) != 2:
            raise ValueError('parking participants absent')
        write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA 20 Hz four-view two-vehicle parking capture'})
        cameras = Cameras(world, carla, ego, site['edge_vehicle_xy'], output)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        native_sha = sha(__file__)
        phase = 'capturing'
        with (output / 'parking-history.jsonl').open('x', buffering=1) as stream:
            for index in range(round(config['duration_s'] * config['rate_hz'])):
                ego_control = control_to(ego, built['requested_endpoint_xy'],
                                         config['engineering_throttle'],
                                         config['engineering_braking_factor'])
                ego.apply_control(carla.VehicleControl(**ego_control))
                edge.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('world frame readback changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                row = {
                    'original_frame': frame, 'time_s': time_s,
                    'ego_id': str(ego.id), 'edge_vehicle_id': str(edge.id),
                    'ego_xy': [ego.get_location().x, ego.get_location().y],
                    'edge_vehicle_xy': [edge.get_location().x, edge.get_location().y],
                    'ego_speed_mps': speed(ego), 'edge_speed_mps': speed(edge),
                    'source_sha256': native_sha,
                    'highway_source_sha256': site['highway_source_sha256'],
                    'map_source_sha256': site['map_source_sha256'],
                    'edge_source_sha256': site['edge_source_sha256'],
                    'ego_control_source_sha256': native_sha,
                    'exception_source_sha256': packet['sources']['authority']['sha256']
                        if case.exception_probe else None,
                    'requested_activity': case.activity,
                    'requested_exception_probe': case.exception_probe}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / 'parking-site.json', packet)
        write(output / 'parking-measurement.json', measure_original(rows, site, case))
        names = ['trace.jsonl', 'video_frames.jsonl', 'parking-history.jsonl',
                 'parking-site.json', 'parking-measurement.json',
                 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name, _, _ in Cameras.SPECS]]
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
        if adapter:
            for actor in reversed(adapter.owned):
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
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={'parking_case': config['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {
                'phase': phase, 'errors': errors, 'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
