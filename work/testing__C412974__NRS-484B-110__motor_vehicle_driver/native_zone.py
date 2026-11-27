"""Original 20 Hz safety-zone travel and four-view acquisition."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from zone_motion import intersection_area, measure_original, validate_scene


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
    """Use reviewed map, physical markers and a motor vehicle under driver control."""

    def __init__(self, world, carla, packet):
        self.world, self.carla, self.packet = world, carla, packet
        self.owned = []

    def place_zone(self, zone):
        if list(zone) != self.packet['scene']['zone_rect_m']:
            raise ValueError('reviewed safety-zone geometry changed')
        for marker in self.packet['zone_markers']:
            blueprint = self.world.get_blueprint_library().find(marker['blueprint_id'])
            location = self.carla.Location(x=marker['xy'][0], y=marker['xy'][1], z=marker.get('z', 0.0))
            prop = self.world.try_spawn_actor(blueprint, self.carla.Transform(location))
            if prop is None or prop.type_id != marker['blueprint_id']:
                raise ValueError('zone marker spawn/readback failed')
            self.owned.append(prop)

    def spawn_vehicle(self, point):
        location = self.carla.Location(x=point[0], y=point[1], z=0)
        waypoint = self.world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed safety-zone approach lacks roadway waypoint')
        location.z = waypoint.transform.location.z + .5
        blueprint_id = self.packet['vehicle_blueprint_id']
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(
            blueprint, self.carla.Transform(location, waypoint.transform.rotation))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError('motor-vehicle spawn/readback failed')
        self.owned.append(actor)
        return actor

    def destroy_all(self):
        errors = []
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        self.owned.clear()
        if errors:
            raise RuntimeError('; '.join(errors))


def control_to(actor, target, halt=False, throttle=.25, braking_factor=5.0):
    position = actor.get_location()
    distance = math.dist((position.x, position.y), target)
    velocity = speed(actor)
    if halt and distance <= 1.25:
        return {'throttle': 0.0, 'brake': 1.0, 'hand_brake': velocity <= .1, 'steer': 0.0}
    braking = halt and distance <= velocity * velocity / braking_factor + 1.5
    return {'throttle': 0.0 if braking else throttle,
            'brake': .65 if braking else 0.0,
            'hand_brake': False, 'steer': steer_to(actor, target)}


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
    rows = []
    errors = []
    phase = 'initializing'
    restored = False
    try:
        archive = output / 'reviewed-site-packet'
        archive.mkdir(exist_ok=False)
        shutil.copy2(packet_path, archive / 'site.json')
        for source in packet['sources'].values():
            path = (packet_path.parent / source['path']).resolve()
            target = archive / source['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        map_record = json.loads((packet_path.parent / packet['sources']['map']['path']).read_text())
        if (world.get_map().name != packet['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != map_record['opendrive_sha256']):
            raise ValueError('reviewed safety-zone map differs from Native world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = packet['scene']
        validate_scene(scene, case)
        adapter = Adapter(world, carla, packet)
        adapter.place_zone(scene['zone_rect_m'])
        ego = adapter.spawn_vehicle(scene['vehicle_start_xy'])
        write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA 20 Hz four-view safety-zone capture'})
        zone = scene['zone_rect_m']
        center_xy = [(zone[0] + zone[2]) / 2, (zone[1] + zone[3]) / 2]
        cameras = Cameras(world, carla, ego, center_xy, output)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        native_sha = sha(Path(__file__))
        phase = 'capturing'
        route = scene['vehicle_route_xy']
        waypoint_index = 1
        with (output / 'safety-zone-history.jsonl').open('x', buffering=1) as stream:
            for index in range(round(config['duration_s'] * config['rate_hz'])):
                pos = ego.get_location()
                if (waypoint_index < len(route) - 1 and
                        math.dist((pos.x, pos.y), route[waypoint_index]) < 2.0):
                    waypoint_index += 1
                target = route[waypoint_index]
                control = control_to(ego, target, halt=waypoint_index == len(route) - 1,
                                     throttle=config['engineering_throttle'],
                                     braking_factor=config['engineering_braking_factor'])
                ego.apply_control(carla.VehicleControl(**control))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('world frame readback changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                body = body_rect(ego)
                row = {
                    'original_frame': frame, 'time_s': time_s,
                    'vehicle_id': str(ego.id), 'vehicle_body_rect_m': body,
                    'vehicle_speed_mps': speed(ego),
                    'zone_overlap_area_m2': intersection_area(body, zone),
                    'frame_source_sha256': native_sha,
                    'vehicle_body_source_sha256': native_sha,
                    'vehicle_motion_source_sha256': native_sha,
                    'zone_boundary_source_sha256': scene['zone_boundary_source_sha256'],
                    'designation_source_sha256': scene['designation_source_sha256'],
                    'marking_visibility_source_sha256': scene['marking_source_sha256'],
                }
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close()
        capture = None
        frame_map.close()
        frame_map = None
        cameras.close()
        cameras = None
        write(output / 'safety-zone-site.json', packet)
        write(output / 'safety-zone-measurement.json', measure_original(rows, scene, case))
        names = ['trace.jsonl', 'video_frames.jsonl', 'safety-zone-history.jsonl',
                 'safety-zone-site.json', 'safety-zone-measurement.json', 'road.xodr',
                 'carla_recorder.log', *[name + '.mkv' for name, _, _ in Cameras.SPECS]]
        names.extend(str(p.relative_to(output)) for p in archive.rglob('*') if p.is_file())
        write(output / 'acquisition.json', {
            name: {'kind': 'original_native', 'sha256': sha(output / name)} for name in names
        })
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
            try:
                adapter.destroy_all()
            except BaseException as error:
                errors.append(repr(error))
        try:
            restored = restore(client, saved_world)['restored']
        except BaseException as error:
            errors.append(repr(error))
        if phase == 'sealed' and not errors and restored:
            seal_capture(
                output, frames=len(rows),
                restoration={'restored': True, 'settings_readback': 'original world snapshot restored'},
                errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                context={'safety_zone_case': config['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {
                'phase': phase, 'errors': errors, 'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
