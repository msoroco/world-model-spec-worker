"""Original source-gated CARLA rear-signal capture and participant readback."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from rear_signal import CASES, construct, measure_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


class Cameras:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, carla, rear, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 1.6, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                pose = carla.Transform(location, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, pose, attach_to=rear if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                        f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                        "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(args, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame differs from original world frame: " + name)
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
                    failures.append("camera encoder failed: " + name)
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
            raise RuntimeError("; ".join(failures))



class Adapter:
    """Translate reviewed scene into two separate Native actors and controls."""

    def __init__(self, world, carla, scene):
        self.world, self.carla, self.scene = world, carla, scene
        self.owned = []
        self.driver = None
        self.route = None
        self.target = None
        self.maneuver = None
        self.policy = None

    def spawn_vehicle(self, xy, role):
        if role not in ('ego', 'rear'):
            raise ValueError('unknown rear-signal role')
        loc = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.world.get_map().get_waypoint(loc, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed one-way participant waypoint absent')
        loc.z = waypoint.transform.location.z + .5
        blueprint_id = self.scene[role + '_blueprint_id']
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint,
                                           self.carla.Transform(loc, waypoint.transform.rotation))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError('reviewed participant blueprint or spawn differs')
        self.owned.append(actor)
        return actor

    def set_route_and_stop(self, ego, route, footprint, maneuver):
        if ego not in self.owned or len(route) < 2 or maneuver not in ('stop', 'sudden_decrease'):
            raise ValueError('reviewed stop/decrease route unsupported')
        self.route = tuple(tuple(point) for point in route)
        self.target = (sum(p[0] for p in footprint) / len(footprint),
                       sum(p[1] for p in footprint) / len(footprint))
        self.maneuver = maneuver

    def set_rear_driver(self, rear, present):
        if rear not in self.owned or type(present) is not bool:
            raise ValueError('rear driver condition differs')
        if present:
            blueprint = self.world.get_blueprint_library().find(self.scene['rear_driver_blueprint_id'])
            pose = self.carla.Transform(self.carla.Location(x=.15, y=-.35, z=1.0))
            self.driver = self.world.try_spawn_actor(blueprint, pose, attach_to=rear)
            if self.driver is None:
                raise ValueError('reviewed rear driver actor spawn failed')
            self.owned.append(self.driver)

    def set_signal_policy(self, ego, policy):
        if ego not in self.owned or policy not in ('before', 'after'):
            raise ValueError('signal policy unsupported')
        self.policy = policy

    def destroy(self, actor):
        actor.destroy()
        self.owned.remove(actor)


def steer_to(actor, xy):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(xy[1] - pose.location.y, xy[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


def rear_relation(ego, rear):
    pose = ego.get_transform()
    dx = pose.location.x - rear.get_location().x
    dy = pose.location.y - rear.get_location().y
    yaw = math.radians(pose.rotation.yaw)
    longitudinal = dx * math.cos(yaw) + dy * math.sin(yaw)
    lateral = -dx * math.sin(yaw) + dy * math.cos(yaw)
    return longitudinal, lateral


def run_native(cfg, scene, scene_path, output, host, port):
    """Acquire original 900-frame two-vehicle signal/motion history."""
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
    adapter = None
    cameras = capture = frame_map = None
    phase, errors, restored = 'initializing', [], False
    rows = []
    try:
        archive = output / 'reviewed-scene-packet'
        archive.mkdir(exist_ok=False)
        shutil.copy2(scene_path, archive / 'scene.json')
        for item in scene['sources'].values():
            source = (Path(scene_path).parent / item['path']).resolve()
            target = archive / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        map_source = Path(scene_path).parent / scene['sources']['map']['path']
        map_record = json.loads(map_source.read_text(encoding='utf-8'))
        if (world.get_map().name != scene['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() !=
                map_record.get('opendrive_sha256')):
            raise ValueError('reviewed rear-signal map differs from Native world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        adapter = Adapter(world, carla, scene)
        suffix = cfg['selected_case_id'].split('__')[-1]
        case = next((x for x in CASES if x.case_id == suffix), None)
        if case is None or scene['rear_vehicle']['driver_present'] != case.rear_driver:
            raise ValueError('reviewed rear driver differs from selected case')
        built = construct(adapter, scene, case)
        ego, rear = built['owned'][:2]
        write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
              'diagnostic_fixture': False, 'method': 'original CARLA live run'})
        cameras = Cameras(world, carla, rear, adapter.target, output)
        capture = PipelineCapture(client, ego, output, cfg['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        phase = 'capturing'
        scene_sha = sha(scene_path)
        native_sha = sha(__file__)
        signal_light = getattr(carla.VehicleLightState, scene['signal_light_name'])
        with (output / 'rear-signal-history.jsonl').open('x', buffering=1) as stream:
            for index in range(round(cfg['duration_s'] * cfg['rate_hz'])):
                signal_onset = 260 if case.signal_policy == 'before' else 320
                ego.set_light_state(signal_light if index >= signal_onset else carla.VehicleLightState.NONE)
                if index < 300:
                    control = {'throttle': .35 if speed(ego) < 8 else 0,
                               'brake': 0, 'steer': steer_to(ego, adapter.route[-1]),
                               'hand_brake': False}
                elif case.maneuver == 'stop':
                    control = {'throttle': 0, 'brake': .85,
                               'steer': steer_to(ego, adapter.target), 'hand_brake': index >= 500}
                else:
                    control = {'throttle': .16 if index >= 350 and speed(ego) < 4 else 0,
                               'brake': .7 if index < 350 else 0,
                               'steer': steer_to(ego, adapter.route[-1]), 'hand_brake': False}
                ego.apply_control(carla.VehicleControl(**control))
                gap, _ = rear_relation(ego, rear)
                rear_control = {'throttle': .2 if speed(rear) < 6 and gap > 6 else 0,
                                'brake': .6 if gap < 5 else 0,
                                'steer': steer_to(rear, (ego.get_location().x, ego.get_location().y)),
                                'hand_brake': False}
                rear.apply_control(carla.VehicleControl(**rear_control))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('original Native frame identity changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                gap, offset = rear_relation(ego, rear)
                displayed = bool(ego.get_light_state() & signal_light)
                visible_proxy = displayed and gap > 0 and abs(offset) < 4
                row = {'original_frame': frame, 'time_s': time_s,
                       'source_sha256': scene_sha, 'ego_motion_source_sha256': native_sha,
                       'rear_motion_source_sha256': native_sha,
                       'signal_source_sha256': scene['signal_device_source_sha256'],
                       'rear_visibility_source_sha256': scene['rear_visibility_source_sha256'],
                       'context_source_sha256': scene['conflict_context_source_sha256'],
                       'route_source_sha256': scene['one_way_route_source_sha256'],
                       'ego_driver_in_control': True,
                       'rear_driver_present': adapter.driver is not None,
                       'ego_id': ego.id, 'rear_id': rear.id,
                       'rear_longitudinal_gap_m': gap, 'rear_lateral_offset_m': offset,
                       'ego_speed_mps': speed(ego), 'rear_speed_mps': speed(rear),
                       'signal_displayed': displayed,
                       'signal_visible_from_rear': visible_proxy,
                       'visibility_method': 'line-of-sight geometry proxy; independent rear-camera pixel review required',
                       'event_marker': case.maneuver if index == 300 else None,
                       'ego_control': control, 'rear_control': rear_control,
                       'rear_driver_actor_id': adapter.driver.id if adapter.driver is not None else None}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / 'rear-signal-scene.json', scene)
        write(output / 'rear-signal-measurement.json', measure_original(rows, scene, case))
        names = ['trace.jsonl', 'video_frames.jsonl', 'rear-signal-history.jsonl',
                 'rear-signal-scene.json', 'rear-signal-measurement.json', 'road.xodr',
                 'carla_recorder.log', *[name + '.mkv' for name, _, _ in Cameras.SPECS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob('*') if path.is_file())
        write(output / 'acquisition.json', {name: {'kind': 'original_native', 'sha256': sha(output / name)}
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
            seal_capture(output, frames=len(rows),
                         restoration={'restored': True, 'settings_readback': 'original world snapshot restored'},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={'rear_signal_case': cfg['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {'phase': phase, 'errors': errors,
                                                       'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
