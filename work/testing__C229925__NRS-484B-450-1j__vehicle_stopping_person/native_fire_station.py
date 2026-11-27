"""Original 20 Hz entrance approach, halt and four-camera acquisition."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from fire_entrance_measurements import measure
from fire_station_scene import construct


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n',
                          encoding='utf-8')


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z)


def vertices(actor):
    return [[v.x, v.y, v.z] for v in
            actor.bounding_box.get_world_vertices(actor.get_transform())]


def control_to(actor, target, *, halt, activity, throttle, braking_factor):
    pose = actor.get_transform()
    location = pose.location
    gap = math.dist((location.x, location.y), target)
    current_speed = speed(actor)
    desired = math.degrees(math.atan2(target[1]-location.y, target[0]-location.x))
    error = ((desired-pose.rotation.yaw+180) % 360)-180
    steer = max(-1.0, min(1.0, error/35.0))
    at_target = halt and gap <= 1.25
    braking = halt and gap <= current_speed*current_speed/braking_factor + 1.5
    return {'throttle': 0.0 if braking or at_target else throttle,
            'brake': 1.0 if at_target else .65 if braking else 0.0,
            'hand_brake': bool(at_target and current_speed <= .1 and
                               activity in ('stand', 'park')),
            'steer': 0.0 if at_target else steer}


class Cameras:
    SPECS = (('overview', 1920, 1080), ('approach', 1280, 720),
             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))

    def __init__(self, world, carla, ego, center, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        poses = ((-16, -14, 25, -48), (-22, -4, 10, -20),
                 (2, -8, 8, -35), (0, 0, 2, 0))
        try:
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x', str(width))
                blueprint.set_attribute('image_size_y', str(height))
                blueprint.set_attribute('fov', '90')
                attached = name == 'driver_reference'
                point = (carla.Location(x=dx, y=dy, z=z) if attached else
                         carla.Location(x=center[0]+dx, y=center[1]+dy, z=z))
                pose = carla.Transform(point, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(blueprint, pose,
                                           attach_to=ego if attached else None)
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
    def __init__(self, world, carla):
        self.world, self.carla = world, carla
        self.owned = []
        self.vehicle = None
        self.traffic = None

    def place_entrance(self, markers, start, end):
        if len(markers) < 2:
            raise ValueError('physical entrance markers absent')
        for marker in markers:
            blueprint = self.world.get_blueprint_library().find(marker['blueprint_id'])
            point = self.carla.Location(x=marker['xy'][0], y=marker['xy'][1],
                                        z=marker.get('z', 0.0))
            prop = self.world.try_spawn_actor(blueprint, self.carla.Transform(point))
            if prop is None or prop.type_id != marker['blueprint_id']:
                raise ValueError('entrance marker spawn/readback failed')
            self.owned.append(prop)

    def spawn_vehicle(self, xy, blueprint_id):
        point = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.world.get_map().get_waypoint(point, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed highway route lacks a waypoint')
        point.z = waypoint.transform.location.z + .5
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint, self.carla.Transform(
            point, waypoint.transform.rotation))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError('reviewed vehicle spawn/readback failed')
        self.owned.append(actor)
        if self.vehicle is None:
            self.vehicle = actor
        else:
            self.traffic = actor
        return actor

    def set_halt_route(self, actor, target, activity):
        if actor is not self.vehicle or activity not in ('stop', 'stand', 'park'):
            raise ValueError('stopping route or activity changed')
        self.halt_target = tuple(target)
        self.activity = activity

    def set_traffic_route(self, actor, target):
        if actor is not self.traffic:
            raise ValueError('conflicting traffic identity changed')
        self.traffic_target = tuple(target)

    def set_context(self, circumstance, authority, person):
        if not person:
            raise ValueError('stopping person source absent')
        self.circumstance = circumstance
        self.authority = authority

    def destroy(self, actor):
        actor.destroy()
        self.owned.remove(actor)


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
    errors, phase, restored = [], 'initializing', False
    frame_count = 0
    try:
        archive = output / 'reviewed-fire-station-packet'
        archive.mkdir(exist_ok=False)
        shutil.copy2(packet_path, archive / 'site.json')
        for source in packet['sources'].values():
            path = (packet_path.parent / source['path']).resolve()
            target = archive / source['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        map_record = json.loads((packet_path.parent / packet['sources']['map']['path']).read_text())
        if (world.get_map().name != packet['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() !=
                map_record['opendrive_sha256']):
            raise ValueError('reviewed fire-station map differs from Native world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        adapter = Adapter(world, carla)
        scene = packet['scene']
        construct(adapter, scene, case)
        ego, traffic = adapter.vehicle, adapter.traffic
        if ego is None or (case.circumstance == 'traffic_conflict' and traffic is None):
            raise ValueError('required original vehicle participant absent')
        write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA 20 Hz four-view fire-station entrance capture'})
        center = [(scene['entrance_start_xy'][0]+scene['entrance_end_xy'][0])/2,
                  (scene['entrance_start_xy'][1]+scene['entrance_end_xy'][1])/2]
        cameras = Cameras(world, carla, ego, center, output)
        capture = PipelineCapture(client, ego, output, config['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        context = dict(scene)
        context.update(case_id=config['selected_case_id'],
                       circumstance=case.circumstance, activity=case.activity)
        write(output / 'fire-entrance-context.json', context)
        phase = 'capturing'
        with (output / 'fire-entrance-trace.jsonl').open('x', buffering=1) as stream:
            for index in range(round(config['duration_s'] * config['rate_hz'])):
                ego_control = control_to(
                    ego, scene['vehicle_target_xy'], halt=True, activity=case.activity,
                    throttle=config['engineering_throttle'],
                    braking_factor=config['engineering_braking_factor'])
                ego.apply_control(carla.VehicleControl(**ego_control))
                if traffic is not None:
                    other_control = control_to(
                        traffic, scene['conflicting_vehicle_target_xy'], halt=False,
                        activity='stop', throttle=config['engineering_throttle'],
                        braking_factor=config['engineering_braking_factor'])
                    traffic.apply_control(carla.VehicleControl(**other_control))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('original world frame readback changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                row = {'frame': frame, 'time_s': time_s,
                       'vehicle_id': str(ego.id),
                       'vehicle_vertices': vertices(ego),
                       'speed_mps': speed(ego),
                       'control_state': ('approach' if index < 10 else case.activity),
                       'control_request': ego_control,
                       'traffic_vehicle_id': str(traffic.id) if traffic else None,
                       'traffic_speed_mps': speed(traffic) if traffic else None,
                       'camera_frame': frame}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                frame_count += 1
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / 'fire-source-receipt.json', {
            'assignment_id': config['assignment_id'],
            'case_id': config['selected_case_id'],
            'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
            'context_sha256': sha(output / 'fire-entrance-context.json'),
            'trace_sha256': sha(output / 'fire-entrance-trace.jsonl'),
            'fps': 20, 'frame_count': frame_count})
        write(output / 'fire-entrance-measurement.json', measure(
            config['selected_case_id'], output / 'fire-entrance-context.json',
            output / 'fire-entrance-trace.jsonl', output / 'fire-source-receipt.json'))
        names = ['trace.jsonl', 'video_frames.jsonl', 'fire-entrance-trace.jsonl',
                 'fire-entrance-context.json', 'fire-source-receipt.json',
                 'fire-entrance-measurement.json', 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name, _, _ in Cameras.SPECS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob('*')
                     if path.is_file())
        write(output / 'acquisition.json', {
            name: {'kind': 'original_native', 'sha256': sha(output / name)}
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
            seal_capture(output, frames=frame_count,
                         restoration={'restored': True,
                                      'settings_readback': 'original world snapshot restored'},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={'fire_station_case': config['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {
                'phase': phase, 'errors': errors, 'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
