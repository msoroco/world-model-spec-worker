"""Exclusive CARLA owner for a separately reviewed C108447 original site.

The reviewed case context supplies exact actor IDs, poses and blueprints. This
module does not choose a parcel, signal, route, purpose or camera position.
"""
from __future__ import annotations

import io
import json
import math
import threading
import time
from pathlib import Path

from native_capture import CAMERAS
from route_controller import apply_carla_control


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pose(carla, values):
    _require(isinstance(values, list) and len(values) == 6 and
             all(type(x) in (int, float) and math.isfinite(x) for x in values),
             'reviewed six-value Native pose required')
    x, y, z, pitch, yaw, roll = values
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


class NativeOwner:
    def __init__(self, host, port, packet, case_id, root, context,
                 *, carla_module=None, capture_class=None):
        self.host, self.port = host, int(port)
        self.packet, self.case_id = packet, case_id
        self.root = Path(root)
        self.context = context
        self.carla = carla_module
        self.capture_class = capture_class
        self.client = self.world = self.ego = self.graph = None
        self.original_settings = None
        self.actors = []
        self.sensors = []
        self._frames = {}
        self._camera_dimensions = {}
        self._condition = threading.Condition()
        self._released = False
        self._release = None

    def __enter__(self):
        if self.carla is None:
            import carla
            self.carla = carla
        if self.capture_class is None:
            from pipeline_capture import PipelineCapture
            self.capture_class = PipelineCapture
        setup = self.context.get('native_setup')
        _require(isinstance(setup, dict) and
                 setup.get('source') and setup.get('reviewed') is True,
                 'separately reviewed Native setup required')
        _require(setup.get('ego_blueprint') and
                 isinstance(setup.get('ego_pose'), list),
                 'reviewed vehicle blueprint and spawn pose required')
        cameras = setup.get('cameras')
        _require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
                 'four reviewed original camera poses required')
        signals = setup.get('signals')
        _require(isinstance(signals, dict) and
                 set(signals) == {'approach_signal', 'destination_signal'} and
                 all(isinstance(value, dict) and type(value.get('actor_id')) is int and
                     value['actor_id'] > 0 and value.get('red_aspect') in
                     ('red_alone', 'red_combined', 'unknown')
                     for value in signals.values()) and
                 len({value['actor_id'] for value in signals.values()}) == 2,
                 'two distinct reviewed original signal actor IDs required')
        try:
            self.client = self.carla.Client(self.host, self.port)
            self.client.set_timeout(30.0)
            self.world = self.client.get_world()
            native_map = self.world.get_map()
            _require(native_map.name == self.packet['native_map']['map_name'],
                     'owner Native map identity differs')
            self.original_settings = self.world.get_settings()
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            blueprints = self.world.get_blueprint_library()
            ego_bp = blueprints.find(setup['ego_blueprint'])
            _require(ego_bp.id.startswith('vehicle.'), 'vehicle blueprint required')
            self.ego = self.world.try_spawn_actor(ego_bp, _pose(self.carla, setup['ego_pose']))
            _require(self.ego is not None, 'reviewed ego pose could not spawn')
            self.actors.append(self.ego)
            self._signal_actors = {}
            for name, signal in signals.items():
                actor = self.world.get_actor(signal['actor_id'])
                _require(actor is not None and actor.type_id.startswith('traffic.traffic_light'),
                         'reviewed signal actor not live')
                self._signal_actors[name] = actor
            for name in CAMERAS:
                item = cameras[name]
                _require(isinstance(item, dict) and isinstance(item.get('pose'), list),
                         'reviewed camera pose required')
                expected = {'overview': (1920, 1080), 'approach': (1280, 720),
                            'reference_corner': (1280, 720),
                            'driver_reference': (1280, 720)}[name]
                _require((item.get('width'), item.get('height')) == expected and
                         item.get('fov_deg') == 90,
                         'reviewed camera differs from selected profile')
                self._camera_dimensions[name] = expected
                bp = blueprints.find('sensor.camera.rgb')
                _require(bp is not None, 'Native RGB camera blueprint unavailable')
                bp.set_attribute('image_size_x', str(item['width']))
                bp.set_attribute('image_size_y', str(item['height']))
                bp.set_attribute('fov', str(item['fov_deg']))
                bp.set_attribute('sensor_tick', '0.05')
                sensor = self.world.spawn_actor(bp, _pose(self.carla, item['pose']))
                _require(sensor is not None, 'reviewed camera pose could not spawn')
                self.sensors.append(sensor)
                sensor.listen(lambda image, camera=name: self._on_image(camera, image))
            self.graph = self.capture_class(self.client, self.ego, self.root,
                                            self.case_id)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _on_image(self, camera, image):
        from PIL import Image
        _require((image.width, image.height) == self._camera_dimensions[camera],
                 'original camera image dimensions differ from selected profile')
        raw = bytes(image.raw_data)
        picture = Image.frombytes('RGBA', (image.width, image.height), raw,
                                  'raw', 'BGRA')
        data = io.BytesIO()
        picture.save(data, format='PNG')
        with self._condition:
            self._frames.setdefault(image.frame, {})[camera] = data.getvalue()
            for old in tuple(self._frames):
                if old < image.frame - 2:
                    del self._frames[old]
            self._condition.notify_all()

    def camera_observer(self, frame, name):
        deadline = time.monotonic() + 10
        with self._condition:
            while name not in self._frames.get(frame, {}):
                remaining = deadline - time.monotonic()
                _require(remaining > 0, 'original camera callback missing for frame')
                self._condition.wait(remaining)
            return self._frames[frame].pop(name)

    def signal_observer(self, frame, name):
        actor = self._signal_actors[name]
        state = str(actor.get_state()).rsplit('.', 1)[-1].lower()
        state = {'red': self.context['native_setup']['signals'][name]['red_aspect'],
                 'yellow': 'yellow',
                 'green': 'green', 'off': 'dark'}.get(state, 'unknown')
        signal_pose = actor.get_transform()
        subject = self.ego.get_location()
        displacement_x = subject.x - signal_pose.location.x
        displacement_y = subject.y - signal_pose.location.y
        forward = signal_pose.get_forward_vector()
        facing = forward.x * displacement_x + forward.y * displacement_y > 0
        return {'device_id': str(actor.id), 'state': state,
                'facing_ego': facing,
                'source': 'original Native traffic-light actor state and transform',
                'original_frame': frame}

    def graph_observer(self, frame, time_s):
        _require(self.graph is not None, 'original graph capture not started')
        self.graph.capture(frame, time_s)

    def control_applier(self, ego, command):
        apply_carla_control(ego, command)

    def __exit__(self, *_):
        errors = []
        if self.graph is not None:
            try:
                self.graph.close()
            except Exception as error:
                errors.append(str(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(str(error))
        for actor in reversed(self.actors):
            try:
                actor.destroy()
            except Exception as error:
                errors.append(str(error))
        if self.world is not None and self.original_settings is not None:
            try:
                self.world.apply_settings(self.original_settings)
            except Exception as error:
                errors.append(str(error))
        restored = False
        if self.world is not None and self.original_settings is not None:
            actual = self.world.get_settings()
            restored = (actual.synchronous_mode == self.original_settings.synchronous_mode and
                        actual.fixed_delta_seconds == self.original_settings.fixed_delta_seconds)
        actors_released = all(not actor.is_alive for actor in self.actors)
        sensors_released = all(not sensor.is_alive for sensor in self.sensors)
        self._released = True
        self._release = {'format': 'native-owner-release-v1', 'case_id': self.case_id,
                         'world_restored': restored, 'actors_released': actors_released,
                         'sensors_released': sensors_released,
                         'readback_passed': restored and actors_released and
                         sensors_released and not errors,
                         'errors': errors}
        return False

    def release_receipt(self):
        _require(self._released, 'owner release readback not complete')
        return self._release


def owner_factory(host, port, packet, case_id, root, context):
    return NativeOwner(host, port, packet, case_id, root, context)


def export_graph(owner, root, attempt, capture):
    manifest = json.loads((Path(root) / 'capture/manifest.json').read_text())
    _require(manifest.get('frames') == capture['sample_count'],
             'owner graph frame count differs from original capture')
    for name in ('capture/evidence.jsonl', 'capture/native/frames.jsonl'):
        path = Path(root) / name
        _require(path.is_file() and len(path.read_text().splitlines()) ==
                 capture['sample_count'], 'owner original graph stream incomplete')
    return {'original_graph_frames': manifest['frames'],
            'physical_acceptance_claimed': False}
