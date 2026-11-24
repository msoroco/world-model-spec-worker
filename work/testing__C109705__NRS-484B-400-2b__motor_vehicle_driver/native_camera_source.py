"""Acquire original CARLA RGB camera PNGs for an exact 20 Hz Native turn.

The camera poses are supplied by a reviewed survey. This lazy boundary owns
sensor actors and never generates an image when a callback is absent.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue

CAMERAS = ('dash', 'front', 'left', 'right')
PROFILE = {'dash': (1920, 1080), 'front': (1280, 720),
           'left': (1280, 720), 'right': (1280, 720)}


class NativeCameraSource:
    def __init__(self, world, carla, survey_path, survey_sha256, output, *, dimensions=None,
                 timeout_s=3.0):
        raw = Path(survey_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != survey_sha256:
            raise ValueError('original camera survey packet hash differs')
        survey = json.loads(raw)
        if survey.get('cell_id') != 'C109705' or survey.get('maneuver') != 'left_turn':
            raise ValueError('original camera survey context differs')
        poses = survey.get('camera_poses')
        if not isinstance(poses, dict) or set(poses) != set(CAMERAS):
            raise ValueError('four source-surveyed camera poses required')
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError('positive original camera timeout required')
        self.poses = poses
        self.world, self.carla = world, carla
        self.output = Path(output)
        self.dimensions = dict(PROFILE if dimensions is None else dimensions)
        if set(self.dimensions) != set(CAMERAS):
            raise ValueError('four original camera dimensions required')
        self.timeout_s = timeout_s
        self.sensors = {}
        self.queues = {name: Queue(maxsize=4) for name in CAMERAS}
        self.closed = False
        self.last_frame = None

    def configure_cameras(self, ego, channels, *, fps):
        if self.closed or self.sensors or tuple(channels) != CAMERAS or fps != 20:
            raise ValueError('exact original four-camera 20 Hz setup required')
        if self.output.exists() and any(self.output.iterdir()):
            raise ValueError('refusing to overwrite original camera sources')
        self.output.mkdir(parents=True, exist_ok=True)
        try:
            for name in CAMERAS:
                pose = self.poses[name]
                if not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'yaw', 'pitch', 'roll'}:
                    raise ValueError(f'original camera pose incomplete: {name}')
                if any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in pose.values()):
                    raise ValueError(f'original camera pose nonfinite: {name}')
                width, height = self.dimensions[name]
                if type(width) is not int or type(height) is not int or width < 1 or height < 1:
                    raise ValueError('original camera dimensions invalid')
                blueprint = self.world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in (('image_size_x', width), ('image_size_y', height),
                                   ('sensor_tick', 0.05)):
                    blueprint.set_attribute(key, str(value))
                transform = self.carla.Transform(
                    self.carla.Location(x=pose['x'], y=pose['y'], z=pose['z']),
                    self.carla.Rotation(yaw=pose['yaw'], pitch=pose['pitch'], roll=pose['roll']))
                sensor = self.world.spawn_actor(blueprint, transform, attach_to=ego)
                self.sensors[name] = sensor
                queue = self.queues[name]
                sensor_id = sensor.id

                def on_image(image, *, target=queue, bound_id=sensor_id):
                    if not target.full():
                        target.put_nowait((bound_id, image))

                sensor.listen(on_image)
        except BaseException:
            self.close()
            raise

    def camera_frame(self, channel, frame):
        if self.closed or channel not in self.sensors or type(frame) is not int:
            raise ValueError('original camera channel or frame invalid')
        try:
            sensor_id, image = self.queues[channel].get(timeout=self.timeout_s)
        except Empty as exc:
            raise ValueError(f'original camera callback absent: {channel}') from exc
        if sensor_id != self.sensors[channel].id or getattr(image, 'frame', None) != frame:
            raise ValueError(f'original camera callback frame mismatch: {channel}')
        width, height = self.dimensions[channel]
        if getattr(image, 'width', None) != width or getattr(image, 'height', None) != height:
            raise ValueError(f'original camera dimensions differ: {channel}')
        path = self.output / channel / f'{frame:08d}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError('original camera frame overwrite refused')
        image.save_to_disk(str(path))
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('original camera PNG missing after callback save')
        return {'frame': frame, 'channel': channel,
                'source_path': str(path.relative_to(self.output.parent)),
                'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for name in reversed(tuple(self.sensors)):
            try:
                self.sensors[name].stop()
                self.sensors[name].destroy()
            except BaseException as exc:
                errors.append(f'{name}: {exc}')
        if errors:
            raise RuntimeError('original camera cleanup failed: ' + '; '.join(errors))
