"""Four synchronized original RGB camera streams for a trail attempt."""
from __future__ import annotations

import math
from pathlib import Path
import queue
import subprocess


CAMERA_SPECS = {'overview': (1920, 1080), 'approach': (1280, 720),
                'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def placements(site):
    box = site['corridor_box_xy']
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    start, end = site['route_xy'][0], site['route_xy'][-1]
    sign = site['sign']['position_xy']
    target = (cx, cy, 1.0)
    positions = {
        'overview': (cx, cy + 18, 25),
        'approach': (start[0] - 6, start[1] - 5, 5),
        'reference_corner': (sign[0] - 3, sign[1] + 5, 5),
        'driver_reference': (end[0] + 5, end[1] - 5, 5),
    }
    result = {}
    for name, point in positions.items():
        dx, dy, dz = (target[i] - point[i] for i in range(3))
        result[name] = {'location_xyz_m': point,
                        'pitch_deg': math.degrees(math.atan2(dz, math.hypot(dx, dy))),
                        'yaw_deg': math.degrees(math.atan2(dy, dx)),
                        'target_xyz_m': target}
    return result


def spawn_cameras(world, site, carla):
    positions = placements(site)
    sensors = {}
    try:
        for name, (width, height) in CAMERA_SPECS.items():
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            if blueprint is None:
                raise ValueError('Native RGB camera blueprint missing')
            for key, value in (('image_size_x', width), ('image_size_y', height), ('fov', 75)):
                blueprint.set_attribute(key, str(value))
            position = positions[name]
            x, y, z = position['location_xyz_m']
            sensor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=position['pitch_deg'], yaw=position['yaw_deg'])))
            if sensor is None:
                raise ValueError(name + ' Native camera spawn failed')
            sensors[name] = sensor
        return sensors
    except BaseException:
        for sensor in reversed(list(sensors.values())):
            sensor.destroy()
        raise


class FourViewJoin:
    def __init__(self, specs=None):
        self.specs = specs or CAMERA_SPECS
        self.previous = None

    def append(self, sample, images):
        frame, time_s = sample['frame'], sample['time_s']
        if self.previous is not None and (
                frame != self.previous[0] + 1 or abs(time_s - self.previous[1] - .05) > .005):
            raise ValueError('four-camera original frame/time discontinuity')
        if set(images) != set(self.specs):
            raise ValueError('four named original camera views required')
        receipt = {'case_id': sample['case_id'], 'frame': frame,
                   'time_s': time_s, 'vehicle_id': sample['vehicle_id'], 'cameras': {}}
        for name, (width, height) in self.specs.items():
            image = images[name]
            if (int(image.frame) != frame or int(image.width) != width or
                    int(image.height) != height or len(image.raw_data) != width * height * 4):
                raise ValueError(name + ' original camera frame or BGRA size differs')
            receipt['cameras'][name] = {'frame': frame, 'width': width,
                                        'height': height, 'pixel_format': 'bgra',
                                        'bytes': len(image.raw_data)}
        self.previous = (frame, time_s)
        return receipt


class FourVideoRecorder:
    def __init__(self, world, site, carla, output, encoder_factory=None):
        self.output = Path(output)
        if not self.output.is_dir() or any((self.output / (name + '.mkv')).exists() for name in CAMERA_SPECS):
            raise ValueError('fresh existing Native attempt required for videos')
        self.sensors, self.encoders, self.queues = {}, {}, {}
        self.errors = []
        self.closed = False
        self.join = FourViewJoin()
        encoder_factory = encoder_factory or subprocess.Popen
        try:
            self.sensors = spawn_cameras(world, site, carla)
            for name, (width, height) in CAMERA_SPECS.items():
                inbox = queue.Queue(maxsize=4)
                self.queues[name] = inbox

                def receive(image, target=inbox, label=name):
                    try:
                        target.put_nowait(image)
                    except queue.Full:
                        self.errors.append('camera queue overflow: ' + label)

                self.sensors[name].listen(receive)
                command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-n', '-f', 'rawvideo', '-pixel_format', 'bgra',
                           '-video_size', f'{width}x{height}', '-framerate', '20',
                           '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra',
                           str(self.output / (name + '.mkv'))]
                self.encoders[name] = encoder_factory(
                    command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, sample, snapshot=None):
        if self.closed or self.errors:
            raise RuntimeError('Native video recorder closed or camera queue failed: ' + '; '.join(self.errors))
        images = {name: self.queues[name].get(timeout=15) for name in CAMERA_SPECS}
        receipt = self.join.append(sample, images)
        for name, image in images.items():
            written = self.encoders[name].stdin.write(image.raw_data)
            if written != len(image.raw_data):
                raise RuntimeError(name + ' encoder wrote incomplete original frame')
        return receipt

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(list(self.sensors.values())):
            try: sensor.stop()
            except BaseException as exc: errors.append('sensor stop: ' + repr(exc))
        for name, encoder in self.encoders.items():
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    errors.append(name + ' encoder failed')
            except BaseException as exc:
                errors.append('encoder close: ' + repr(exc))
        for sensor in reversed(list(self.sensors.values())):
            try: sensor.destroy()
            except BaseException as exc: errors.append('sensor destroy: ' + repr(exc))
        if errors:
            raise RuntimeError('; '.join(errors))
