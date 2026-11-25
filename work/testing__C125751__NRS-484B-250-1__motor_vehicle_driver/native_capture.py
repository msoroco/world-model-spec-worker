"""Original Native four-camera acquisition for source-reviewed C125751 cases."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from native_driver import apply_ego, apply_other, body_polygon, control_step
from signal_crossing import construct_native
from source_bindings import bind_sources, validate_review_refs


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


class CameraBank:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, ego, output, carla, scene):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        self.closed = False
        try:
            self._start(world, ego, Path(output), carla, scene)
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    def _start(self, world, ego, output, carla, scene):
        library = world.get_blueprint_library()
        bounds = scene["crossing"]["bounds_xy_m"]
        center = ((bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2)
        start = scene["ego_route_xy_m"][0]
        poses = {"overview": (center[0], center[1], 45, -90, 0),
                 "approach": (start[0], start[1], 12, -25,
                              math.degrees(math.atan2(center[1]-start[1], center[0]-start[0]))),
                 "reference_corner": (bounds[0]-4, bounds[1]-4, 12, -35,
                                      math.degrees(math.atan2(center[1]-bounds[1]+4,
                                                               center[0]-bounds[0]+4))),
                 "driver_reference": (0, 0, 2, 0, 0)}
        for name, width, height in self.SPECS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height), ("fov", 90)):
                bp.set_attribute(key, str(value))
            x, y, z, pitch, yaw = poses[name]
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=pitch, yaw=yaw))
            sensor = world.spawn_actor(bp, transform,
                                       attach_to=ego if name == "driver_reference" else None)
            if sensor is None:
                raise RuntimeError("Native camera spawn failed: " + name)
            self.sensors.append(sensor)
            frames = queue.Queue(maxsize=4)
            self.queues[name] = frames
            def receive(image, q=frames, label=name):
                try:
                    q.put_nowait(image)
                except queue.Full:
                    self.errors.append("camera queue overflow: " + label)
            sensor.listen(receive)
            self.encoders[name] = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                 f"{width}x{height}", "-framerate", "20", "-i", "pipe:0", "-an",
                 "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        images = {}
        for name, width, height in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError(name + " camera frame differs from world frame")
            if image.width != width or image.height != height:
                raise RuntimeError(name + " camera dimensions differ from capture contract")
            raw = image.raw_data
            if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != width * height * 4:
                raise RuntimeError(name + " camera BGRA byte count differs from capture contract")
            images[name] = raw
        for name, _, _ in self.SPECS:
            self.encoders[name].stdin.write(images[name])

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as exc:
                errors.append(repr(exc))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    errors.append("camera encoder failed: " + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


def _resolve_signal(world, item):
    identifier = str(item['id'])
    matches = []
    for actor in world.get_actors().filter('traffic.traffic_light*'):
        opendrive_id = (str(actor.get_opendrive_id())
                        if hasattr(actor, 'get_opendrive_id') else None)
        if identifier in (opendrive_id, str(actor.id)):
            matches.append(actor)
    if len(matches) != 1:
        raise ValueError('reviewed official signal does not resolve uniquely')
    return matches[0]


def _spawn(world, spec, carla, party, transform):
    identifier = spec[party + '_blueprint']
    blueprint = world.get_blueprint_library().find(identifier)
    if blueprint is None:
        raise ValueError('reviewed Native vehicle blueprint absent: ' + identifier)
    blueprint.set_attribute('role_name', 'c125751_250_1_' + party)
    return world.spawn_actor(blueprint, transform)


def run_native(spec, suffix, sources, camera_plan, output, host, port):
    """Acquire originals; saved processing alone may interpret measurements."""
    packet = bind_sources(spec, suffix, sources, camera_plan)
    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Native attempt lacks materialized construction')
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import equal, fields

    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    actors = {}
    cameras = capture = frame_map = device = None
    original_signal_state = original_signal_frozen = None
    rows = []
    phase = 'initializing'
    failure = None
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        constructed = construct_native(
            world, packet, Path(sources, 'map.xodr').read_bytes(),
            Path(sources, 'review.json').read_bytes(),
            lambda x, y: carla.Location(x=x, y=y, z=0), _resolve_signal,
            lambda party, transform: _spawn(world, spec, carla, party, transform))
        actors, device = constructed['actors'], constructed['device']
        original_signal_state = device.get_state()
        original_signal_frozen = device.is_frozen()
        device.freeze(True)
        device.set_state(getattr(carla.TrafficLightState, spec['ego_light_request']))
        if str(device.get_state()).split('.')[-1] != spec['ego_light_request']:
            raise ValueError('live signal request readback differs')
        for name in ('source-packet.json', 'review.json', 'map.xodr'):
            if (output / name).exists():
                raise ValueError('retained reviewed source already exists: ' + name)
            (output / name).write_bytes(Path(sources, name).read_bytes())
        (output / 'reviewed-packet.json').write_bytes((output / 'source-packet.json').read_bytes())
        write(output / 'source-bindings.json', {
            'case_id': spec['case_id'],
            'source_packet_sha256': spec['source_packet_sha256'],
            'map_sha256': spec['map_sha256'],
            'review_sha256': packet['review_sha256'],
            'crossing_id': spec['crossing_id'],
            'ego_route_sha256': spec['ego_route_sha256'],
            'other_route_sha256': spec['other_route_sha256'],
            'camera_plan_sha256': spec['camera_plan_sha256'],
            'ego_blueprint': spec['ego_blueprint'],
            'other_blueprint': spec['other_blueprint'],
        })
        retained_refs = []
        for ref in validate_review_refs((output / 'review.json').read_bytes(), sources):
            name = ref['path']
            if name != 'map.xodr':
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise ValueError('retained reviewed source already exists: ' + name)
                destination.write_bytes(Path(sources, name).read_bytes())
            retained_refs.append(name)
        write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA capture with separately reviewed source bytes',
            'review_sha256': sha(output / 'review.json')})
        scene = {'crossing': {'bounds_xy_m': packet['crossing_bounds_xy_m']},
                 'ego_route_xy_m': packet['ego_route_xy_m']}
        apply_ego(actors['ego'], carla, 'brake')
        cameras = CameraBank(world, actors['ego'], output, carla, scene)
        capture = PipelineCapture(client, actors['ego'], output, spec['case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        phase = 'capturing'
        state = {}
        other_target = 1
        for index in range(spec['duration_frames']):
            if suffix == 'signal_red' and index == 100:
                device.set_state(carla.TrafficLightState.Green)
            other_target = apply_other(
                actors['other'], carla, packet['other_route_xy_m'],
                release=suffix != 'other_later' or state.get('ego_entered', False),
                target_index=other_target)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise RuntimeError('Native world tick identity differs')
            time_s = snapshot.timestamp.elapsed_seconds
            capture.capture(frame, time_s)
            cameras.append(frame)
            frame_map.append(frame, time_s)
            ego_body, other_body = (body_polygon(actors[party]) for party in ('ego', 'other'))
            light = str(device.get_state()).split('.')[-1]
            state = control_step(spec, packet, state, frame=index,
                                 ego_body=ego_body, other_body=other_body,
                                 light_readback=light)
            apply_ego(actors['ego'], carla, state['request'])
            rows.append({'frame': index, 'time_s': time_s,
                         'ego_light_readback': light,
                         'ego_next_tick_request': state['request'],
                         **{party: {'actor_id': int(actors[party].id), 'alive': actors[party].is_alive,
                                    'xy_m': [actors[party].get_transform().location.x,
                                             actors[party].get_transform().location.y],
                                    'body_vertices_xy_m': body}
                            for party, body in (('ego', ego_body), ('other', other_body))}})
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        history = {'map_sha256': packet['map_sha256'],
                   'crossing_id': packet['crossing_id'],
                   'crossing_bounds_xy_m': packet['crossing_bounds_xy_m'],
                   'ego_actor_id': int(actors['ego'].id),
                   'other_actor_id': int(actors['other'].id), 'frames': rows}
        (output / 'signal-history.json').write_text(json.dumps(history, allow_nan=False))
        history_sha = sha(output / 'signal-history.json')
        write(output / 'signal-packet.json', {
            'payload_sha256': history_sha, 'case_id': spec['case_id'],
            'review_sha256': packet['review_sha256'],
            'map_sha256': packet['map_sha256'],
            'expected_frames': spec['duration_frames'],
            'crossing_id': packet['crossing_id'],
            'ego_route_sha256': spec['ego_route_sha256'],
            'other_route_sha256': spec['other_route_sha256'],
            'camera_plan_sha256': spec['camera_plan_sha256'],
            'duration_frames': spec['duration_frames'],
            'ego_blueprint': spec['ego_blueprint'],
            'other_blueprint': spec['other_blueprint']})
        names = ('signal-history.json', 'signal-packet.json', 'source-packet.json',
                 'source-bindings.json',
                 'reviewed-packet.json',
                 'acquisition-provenance.json',
                 'review.json', 'map.xodr', 'trace.jsonl', 'video_frames.jsonl',
                 'road.xodr', 'carla_recorder.log',
                 *retained_refs,
                 *(name + '.mkv' for name, *_ in CameraBank.SPECS))
        write(output / 'acquisition.json', {name: {'kind': 'original_native',
                                                   'sha256': sha(output / name)}
                                            for name in set(names)})
        phase = 'sealed'
    except BaseException as exc:
        failure = repr(exc)
        raise
    finally:
        cleanup = []
        for resource in (capture, frame_map, cameras):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    cleanup.append(repr(exc))
        for actor in reversed(list(actors.values())):
            try:
                actor.destroy()
            except BaseException as exc:
                cleanup.append(repr(exc))
        if device is not None and original_signal_state is not None:
            try:
                device.set_state(original_signal_state)
                device.freeze(original_signal_frozen)
                if device.get_state() != original_signal_state or device.is_frozen() != original_signal_frozen:
                    cleanup.append('signal state restoration readback differs')
            except BaseException as exc:
                cleanup.append(repr(exc))
        try:
            world.apply_settings(original_settings)
            restored = all(equal(fields(world.get_settings()).get(key), value)
                           for key, value in fields(original_settings).items())
        except BaseException as exc:
            cleanup.append(repr(exc))
        if phase == 'sealed' and not cleanup and restored:
            seal_capture(output, frames=len(rows),
                         restoration={'restored': True,
                                      'settings_readback': 'synchronous mode and delta restored'},
                         errors=[], encoder_exit_codes={name: 0 for name, *_ in CameraBank.SPECS},
                         context={'crossing_id': packet['crossing_id'],
                                  'review_sha256': packet['review_sha256']})
        else:
            write(output / 'native-run-status.json', {
                'phase': phase, 'errors': [item for item in [failure, *cleanup] if item],
                'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or settings restoration failed')
