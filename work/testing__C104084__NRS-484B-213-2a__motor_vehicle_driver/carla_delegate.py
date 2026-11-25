"""Lazy, exclusively owned CARLA delegate for reviewed C104084 crest captures.

The reviewed packet supplies actor/camera poses and route points. This module
never selects a highway, crest, opposing lane, or legal hazard distance.
"""
from __future__ import annotations

import math
import hashlib
import subprocess
import threading
import time
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pose(carla, values):
    require(isinstance(values, list) and len(values) == 6 and
            all(type(v) in (int, float) and math.isfinite(v) for v in values),
            'reviewed six-coordinate Native pose required')
    x, y, z, pitch, yaw, roll = values
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def point(carla, values):
    require(isinstance(values, list) and len(values) == 3 and
            all(type(v) in (int, float) and math.isfinite(v) for v in values),
            'reviewed three-coordinate Native point required')
    return carla.Location(x=values[0], y=values[1], z=values[2])


class CarlaDelegate:
    """Own two vehicles, four original RGB sensors and synchronous world state."""

    def __init__(self, client, packet, case_id, output, *, carla_module=None,
                 graph_root=None, graph_capture_class=None):
        self.client = client
        self.packet = packet
        self.case_id = case_id
        self.output = Path(output)
        self.carla = carla_module
        self.graph_root = Path(graph_root) if graph_root is not None else None
        self.graph_capture_class = graph_capture_class
        self.graph = None
        self.world = None
        self.saved_settings = None
        self.saved_weather = None
        self.actors = []
        self.sensors = []
        self.ego = self.other = None
        self._frames = {}
        self._encoders = {}
        self._condition = threading.Condition()
        self._context = None
        self._last_frame = None
        self._release = None
        self._route_indices = {'ego': 0, 'other': 0}
        self._png_hashes = {name: {} for name in CAMERAS}

    def _setup(self):
        setup = self.packet.get('native_setup')
        require(isinstance(setup, dict) and setup.get('reviewed') is True and
                setup.get('reviewer') and setup.get('source_citation'),
                'separately reviewed Native setup required')
        require(setup.get('map_opendrive_sha256') == self.packet.get('map_opendrive_sha256'),
                'Native setup and reviewed road hash differ')
        for name in ('ego', 'other'):
            actor = setup.get(name)
            require(isinstance(actor, dict) and str(actor.get('blueprint', '')).startswith('vehicle.'),
                    'reviewed vehicle blueprint required: ' + name)
            pose(self.carla, actor.get('pose'))
            route = actor.get('route')
            require(isinstance(route, list) and len(route) >= 2,
                    'reviewed original route required: ' + name)
            for values in route:
                point(self.carla, values)
        cameras = setup.get('cameras')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
                'four reviewed original cameras required')
        for name in CAMERAS:
            item = cameras[name]
            require(isinstance(item, dict), 'reviewed camera record required')
            pose(self.carla, item.get('pose'))
            require(type(item.get('width')) is int and type(item.get('height')) is int and
                    (item['width'], item['height']) == SIZES[name] and
                    type(item.get('fov_deg')) in (int, float) and 1 <= item['fov_deg'] <= 170,
                    'reviewed camera differs from pinned full-resolution profile')
        line = setup.get('center_reference')
        require(isinstance(line, dict) and line.get('source_ref') and
                isinstance(line.get('point'), list) and isinstance(line.get('overview'), list),
                'reviewed center reference required')
        point(self.carla, line['point'])
        require(len(line['overview']) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in line['overview']) and
                math.hypot(*line['overview']) > .5, 'reviewed center direction invalid')
        return setup

    def begin(self, case_id):
        require(case_id == self.case_id == self.packet.get('case_id'),
                'exact Native crest case mismatch')
        if self.carla is None:
            import carla
            self.carla = carla
        setup = self._setup()
        try:
            self.world = self.client.get_world()
            require(self.world.get_map().to_opendrive() and
                    __import__('hashlib').sha256(self.world.get_map().to_opendrive().encode()).hexdigest() ==
                    self.packet['map_opendrive_sha256'], 'live Native road differs from reviewed source')
            self.saved_settings = self.world.get_settings()
            self.saved_weather = self.world.get_weather()
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            library = self.world.get_blueprint_library()
            for name in ('ego', 'other'):
                item = setup[name]
                actor = self.world.try_spawn_actor(library.find(item['blueprint']),
                                                   pose(self.carla, item['pose']))
                require(actor is not None, 'reviewed Native vehicle pose could not spawn: ' + name)
                self.actors.append(actor)
                setattr(self, name, actor)
            for name in CAMERAS:
                item = setup['cameras'][name]
                video = self.output / f'{name}.mkv'
                command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo',
                           '-pix_fmt', 'bgra', '-s', f"{item['width']}x{item['height']}",
                           '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'libx264rgb',
                           '-preset', 'ultrafast', '-qp', '0', '-pix_fmt',
                           'rgb24', '-y', str(video)]
                self._encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                         stderr=subprocess.PIPE)
                bp = library.find('sensor.camera.rgb')
                for key, value in (('image_size_x', item['width']),
                                   ('image_size_y', item['height']),
                                   ('fov', item['fov_deg']), ('sensor_tick', .05)):
                    bp.set_attribute(key, str(value))
                sensor = self.world.spawn_actor(bp, pose(self.carla, item['pose']))
                require(sensor is not None, 'reviewed Native camera could not spawn: ' + name)
                self.sensors.append(sensor)
                sensor.listen(lambda image, camera=name: self._on_image(camera, image))
            if self.graph_root is not None:
                if self.graph_capture_class is None:
                    from pipeline_capture import PipelineCapture
                    self.graph_capture_class = PipelineCapture
                self.graph = self.graph_capture_class(self.client, self.ego,
                                                      self.graph_root, self.case_id)
            sources = self.packet['sources']
            one_way = case_id.endswith('__left_one_way_obstructed')
            self._context = {'case_id': case_id, 'law_id': self.packet['law_id'],
                             'highway_source_ref': sources['highway']['sha256'],
                             'center_reference_source_ref': sources['center_reference']['sha256'],
                             'lane_allocation': 'one_way' if one_way else 'two_way'}
            if one_way:
                self._context['one_way_authority'] = {
                    'sha256': sources['one_way_authority']['sha256'],
                    'source_ref': sources['one_way_authority']['source_citation']}
            else:
                self._context['opposing_lane_source_ref'] = sources['opposing_lane']['sha256']
            return self._context
        except BaseException:
            self.close()
            raise

    def _on_image(self, camera, image):
        from PIL import Image
        item = self.packet['native_setup']['cameras'][camera]
        require((image.width, image.height) == (item['width'], item['height']),
                'original camera size differs')
        with self._condition:
            prior = self._frames.get(image.frame, {})
            require(camera not in prior, 'duplicate original camera callback')
            raw = bytes(image.raw_data)
            folder = self.output / 'original-png' / camera
            folder.mkdir(parents=True, exist_ok=True)
            png = folder / f'{image.frame:08d}.png'
            require(not png.exists(), 'original camera PNG already exists')
            Image.frombytes('RGBA', (image.width, image.height), raw,
                            'raw', 'BGRA').save(png, format='PNG')
            self._png_hashes[camera][str(image.frame)] = hashlib.sha256(png.read_bytes()).hexdigest()
            self._encoders[camera].stdin.write(raw)
            self._frames.setdefault(image.frame, {})[camera] = True
            self._condition.notify_all()

    def tick(self):
        require(self.world is not None, 'Native owner not started')
        for name in ('ego', 'other'):
            self._apply_reviewed_route(name)
        frame = self.world.tick()
        require(type(frame) is int and (self._last_frame is None or frame == self._last_frame + 1),
                'Native world frame gap')
        self._last_frame = frame
        return frame

    def _apply_reviewed_route(self, name):
        actor = getattr(self, name)
        route = self.packet['native_setup'][name]['route']
        index = self._route_indices[name]
        here = actor.get_location()
        while index < len(route) - 1 and math.hypot(route[index][0] - here.x,
                                                     route[index][1] - here.y) < 2:
            index += 1
        self._route_indices[name] = index
        target = route[index]
        distance = math.hypot(target[0] - here.x, target[1] - here.y)
        if index == len(route) - 1 and distance < 2:
            actor.apply_control(self.carla.VehicleControl(throttle=0.0, brake=1.0,
                                                          steer=0.0))
            return
        yaw = math.radians(actor.get_transform().rotation.yaw)
        heading = math.atan2(target[1] - here.y, target[0] - here.x)
        error = math.atan2(math.sin(heading - yaw), math.cos(heading - yaw))
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        target_speed = self.packet['native_setup'][name].get('target_speed_mps')
        require(type(target_speed) in (int, float) and 0 < target_speed <= 15,
                'reviewed target speed required')
        throttle = min(.5, max(0.0, .25 * (target_speed - speed)))
        brake = min(.5, max(0.0, .25 * (speed - target_speed)))
        steer = max(-.8, min(.8, error * .7))
        actor.apply_control(self.carla.VehicleControl(throttle=throttle,
                                                      brake=brake, steer=steer))

    def camera_frames(self, frame):
        deadline = time.monotonic() + 10
        with self._condition:
            while set(self._frames.get(frame, {})) != set(CAMERAS):
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'four original camera callbacks missing')
                self._condition.wait(remaining)
            return {name: frame for name in CAMERAS}

    def graph_observer(self, frame, time_s):
        require(self.graph is not None, 'original Native graph capture missing')
        self.graph.capture(frame, time_s)

    def _signed_corners(self):
        center = self.packet['native_setup']['center_reference']
        origin = center['point']
        fx, fy = center['overview']
        length = math.hypot(fx, fy)
        nx, ny = -fy / length, fx / length
        box = self.ego.bounding_box
        transform = self.ego.get_transform()
        extent = box.extent
        result = []
        for x in (-extent.x, extent.x):
            for y in (-extent.y, extent.y):
                p = transform.transform(self.carla.Location(x=x + box.location.x,
                                                             y=y + box.location.y,
                                                             z=box.location.z))
                result.append((p.x - origin[0]) * nx + (p.y - origin[1]) * ny)
        return result

    def sample(self, frame):
        require(frame == self._last_frame, 'sample must use current Native frame')
        ego = self.ego.get_location()
        other = self.other.get_location()
        corners = self._signed_corners()
        distance = math.sqrt((ego.x-other.x)**2 + (ego.y-other.y)**2 + (ego.z-other.z)**2)
        hits = []
        eye = self.carla.Location(x=ego.x, y=ego.y, z=ego.z+1.4)
        box = self.other.bounding_box
        transform = self.other.get_transform()
        for x in (-box.extent.x, box.extent.x):
            for y in (-box.extent.y, box.extent.y):
                target = transform.transform(self.carla.Location(x=x+box.location.x,
                                                                  y=y+box.location.y,
                                                                  z=box.location.z+1.4))
                collisions = self.world.cast_ray(eye, target)
                hits.append(any(getattr(hit, 'label', None) != self.carla.CityObjectLabel.Vehicles
                                for hit in collisions))
        timestamp = self.world.get_snapshot().timestamp.elapsed_seconds
        body = {'frame': frame, 'timestamp_s': timestamp,
                'ego_body_corners_signed_m': corners,
                'opposing_body_distance_m': distance,
                'ego_source_ref': f'Native actor {self.ego.id}',
                'opposing_source_ref': f'Native actor {self.other.id}'}
        ray = {'frame': frame, 'body_corner_ray_hits': hits,
               'ray_source_ref': 'Native world.cast_ray at original frame ' + str(frame)}
        return body, ray

    def write_camera_video(self, camera, path):
        require(camera in CAMERAS and self._last_frame is not None,
                'original camera or frame missing')
        item = self.packet['native_setup']['cameras'][camera]
        frames = sorted(self._frames)
        require(frames and frames == list(range(frames[0], frames[-1]+1)),
                'original camera frame sequence incomplete')
        require(all(camera in self._frames[frame] for frame in frames),
                'original camera image missing')
        require(Path(path) == self.output / f'{camera}.mkv',
                'original camera output path differs')
        process = self._encoders.pop(camera)
        process.stdin.close()
        error = process.stderr.read()
        code = process.wait()
        process.stderr.close()
        require(code == 0, 'original camera encoder failed: ' + error.decode(errors='replace')[-500:])
        if camera == CAMERAS[-1]:
            import json
            manifest = {'format': 'c104084-original-camera-pngs-v1',
                        'case_id': self.case_id,
                        'frames': {name: self._png_hashes[name] for name in CAMERAS}}
            (self.output / 'original-png-manifest.json').write_text(
                json.dumps(manifest, sort_keys=True) + '\n', encoding='utf-8')

    def close(self):
        errors = []
        if self.graph is not None:
            try:
                self.graph.close()
            except Exception as exc:
                errors.append(str(exc))
            self.graph = None
        for process in self._encoders.values():
            try:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdin.close()
                process.stderr.close()
            except Exception as exc:
                errors.append(str(exc))
        self._encoders.clear()
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as exc:
                errors.append(str(exc))
        for actor in reversed(self.actors):
            try:
                actor.destroy()
            except Exception as exc:
                errors.append(str(exc))
        if self.world is not None and self.saved_settings is not None:
            try:
                self.world.apply_settings(self.saved_settings)
                self.world.set_weather(self.saved_weather)
                actual = self.world.get_settings()
                require(actual.synchronous_mode == self.saved_settings.synchronous_mode and
                        actual.fixed_delta_seconds == self.saved_settings.fixed_delta_seconds,
                        'Native world settings restoration readback differs')
            except Exception as exc:
                errors.append(str(exc))
        self._release = {'world_restored': not errors,
                         'actors_released': all(not a.is_alive for a in self.actors),
                         'sensors_released': all(not s.is_alive for s in self.sensors),
                         'errors': errors}
        require(not errors and self._release['actors_released'] and
                self._release['sensors_released'], 'Native owner release failed')

    def release_receipt(self):
        require(self._release is not None, 'Native release readback pending')
        return self._release
