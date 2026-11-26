"""Original source-gated CARLA capture for exact access-aisle probes."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from access_aisle import CASES, construct, measure_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def xy_body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    x = [v.x for v in vertices]
    y = [v.y for v in vertices]
    return [[min(x), min(y)], [max(x), min(y)], [max(x), max(y)], [min(x), max(y)]]


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


class Cameras:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, carla, ego, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 2, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                pose = carla.Transform(location, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, pose, attach_to=ego if attached else None)
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
    """Translate construction calls into exact Native actor and route controls."""

    def __init__(self, world, carla, site):
        self.world, self.carla, self.site = world, carla, site
        self.owned = []
        self.route = None
        self.target = None
        self.activity = None

    def spawn_vehicle(self, xy, role):
        if role != 'ego':
            raise ValueError('only exact ego vehicle may be constructed')
        loc = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.world.get_map().get_waypoint(loc, project_to_road=False)
        if waypoint is None:
            raise ValueError('reviewed one-way approach absent from Native map')
        loc.z = waypoint.transform.location.z + .5
        blueprint = self.world.get_blueprint_library().find(self.site['vehicle_blueprint_id'])
        actor = self.world.try_spawn_actor(blueprint,
                                           self.carla.Transform(loc, waypoint.transform.rotation))
        if actor is None or actor.type_id != self.site['vehicle_blueprint_id']:
            raise ValueError('reviewed ego blueprint/spawn failed Native readback')
        self.owned.append(actor)
        return actor

    def set_parking_route(self, ego, route, target_footprint):
        if ego not in self.owned or len(route) < 2:
            raise ValueError('reviewed parking route missing')
        self.route = tuple(tuple(point) for point in route)
        xs = [p[0] for p in target_footprint]
        ys = [p[1] for p in target_footprint]
        self.target = (sum(xs) / len(xs), sum(ys) / len(ys))

    def request_activity(self, ego, activity):
        if ego not in self.owned or activity not in ('park', 'loading_stop', 'travel'):
            raise ValueError('access-aisle activity unsupported')
        self.activity = activity

    def destroy(self, actor):
        actor.destroy()
        self.owned.remove(actor)


def steer_to(actor, xy):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(xy[1] - pose.location.y, xy[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


def run_native(cfg, site, site_path, output, host, port):
    """Capture 900 original frames; source review and physical acceptance remain separate."""
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
    actors = []
    cameras = capture = frame_map = None
    phase = 'initializing'
    errors = []
    restored = False
    rows = []
    try:
        if sha(site_path) != cfg.get('reviewed_site_sha256', sha(site_path)):
            raise ValueError('reviewed site packet hash changed')
        archive = output / 'reviewed-site-packet'
        archive.mkdir(exist_ok=False)
        shutil.copy2(site_path, archive / 'site.json')
        for item in site['sources'].values():
            source = (Path(site_path).parent / item['path']).resolve()
            target = archive / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        source_map = Path(site_path).parent / site['sources']['map']['path']
        map_record = json.loads(source_map.read_text(encoding='utf-8'))
        if (world.get_map().name != site['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() !=
                map_record.get('opendrive_sha256')):
            raise ValueError('reviewed access-aisle map differs from Native world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        adapter = Adapter(world, carla, site)
        suffix = cfg['selected_case_id'].split('__')[-1]
        case = next((item for item in CASES if item.case_id == suffix), None)
        if case is None or site.get('requested_activity') != case.requested_activity or site.get('requested_footprint') != case.target:
            raise ValueError('reviewed site differs from selected activity/footprint')
        built = construct(adapter, site, case)
        ego = built['ego']
        actors.extend(adapter.owned)
        target = adapter.target
        target_wp = world.get_map().get_waypoint(carla.Location(x=target[0], y=target[1], z=0),
                                                  project_to_road=False)
        if target_wp is None:
            raise ValueError('reviewed target footprint is not reachable from Native road')
        worker = None
        if case.requested_activity == 'loading_stop':
            start = site.get('loading_person_start_xy')
            end = site.get('loading_person_end_xy')
            if not (isinstance(start, list) and isinstance(end, list) and len(start) == len(end) == 2
                    and math.dist(start, end) >= 2):
                raise ValueError('reviewed loading person path required')
            blueprint = world.get_blueprint_library().find(site['loading_person_blueprint_id'])
            worker = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=start[0], y=start[1], z=.5)))
            actors.append(worker)
        write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
              'diagnostic_fixture': False, 'method': 'original CARLA live run'})
        cameras = Cameras(world, carla, ego, target, output)
        capture = PipelineCapture(client, ego, output, cfg['selected_case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        phase = 'capturing'
        native_code_sha = sha(Path(__file__))
        site_sha = sha(site_path)
        with (output / 'access-aisle-history.jsonl').open('x', buffering=1) as stream:
            for index in range(round(cfg['duration_s'] * cfg['rate_hz'])):
                current = ego.get_transform().location
                distance = math.dist((current.x, current.y), target)
                if case.requested_activity == 'travel':
                    waypoint = adapter.route[-1]
                    command = {'throttle': .28 if speed(ego) < 4 else 0.0, 'brake': 0.0,
                               'hand_brake': False, 'steer': steer_to(ego, waypoint)}
                elif distance <= 1.3:
                    command = {'throttle': 0.0, 'brake': 1.0,
                               'hand_brake': case.requested_activity == 'park', 'steer': 0.0}
                else:
                    braking = distance <= speed(ego) ** 2 / 5 + 1.5
                    command = {'throttle': 0.0 if braking else .25, 'brake': .65 if braking else 0.0,
                               'hand_brake': False, 'steer': steer_to(ego, target)}
                ego.apply_control(carla.VehicleControl(**command))
                if worker is not None and distance <= 1.3:
                    fraction = min(1.0, max(0.0, (index - 300) / 100))
                    start, end = site['loading_person_start_xy'], site['loading_person_end_xy']
                    worker.set_transform(carla.Transform(carla.Location(
                        x=start[0] + fraction * (end[0] - start[0]),
                        y=start[1] + fraction * (end[1] - start[1]), z=.5)))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native frame identity changed')
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                body = xy_body(ego)
                velocity = speed(ego)
                loading_distance = (math.dist((worker.get_location().x, worker.get_location().y),
                                              (ego.get_location().x, ego.get_location().y))
                                    if worker is not None else None)
                activity = ('travel' if case.requested_activity == 'travel' and velocity > .1 else
                            'loading_stop' if loading_distance is not None and loading_distance < 2 and velocity <= .1 else
                            'park' if ego.get_control().hand_brake and velocity <= .1 else 'approach')
                row = {'original_frame': frame, 'time_s': time_s,
                       'source_sha256': site_sha, 'body_geometry_source_sha256': native_code_sha,
                       'control_source_sha256': site['sources']['activity_plan']['sha256'],
                       'activity_source_sha256': site['sources']['activity_plan']['sha256'],
                       'map_source_sha256': site['map_source_sha256'],
                       'aisle_marking_source_sha256': site['aisle_marking_source_sha256'],
                       'ego_id': ego.id, 'ego_speed_mps': velocity,
                       'observed_activity': activity, 'vehicle_body_polygon_xy': body,
                       'control_command': command,
                       'loading_person_id': worker.id if worker is not None else None,
                       'loading_person_distance_m': loading_distance}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / 'access-aisle-site.json', site)
        write(output / 'access-aisle-measurement.json', measure_original(rows, site, case))
        names = ['trace.jsonl', 'video_frames.jsonl', 'access-aisle-history.jsonl',
                 'access-aisle-site.json', 'access-aisle-measurement.json', 'road.xodr',
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
        for actor in reversed(actors):
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
                         context={'access_aisle_case': cfg['selected_case_id']})
        else:
            write(output / 'native-run-status.json', {'phase': phase, 'errors': errors,
                                                       'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
