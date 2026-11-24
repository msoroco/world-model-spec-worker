"""Synchronized four-camera Native readback and lossless saved media.

Sensors must already be attached to the ego by native_site.construct. Original
CARLA BGRA bytes are written in frame order; no synthetic image is substituted.
"""
from __future__ import annotations

import queue
import subprocess
from pathlib import Path

from delivery_audit import CAMERAS

PROFILE = {'front': (1920, 1080), 'front_left': (1280, 720),
           'front_right': (1280, 720), 'rear': (1280, 720)}


class NativeMedia:
    def __init__(self, sensors, attempt: Path, *, diagnostic_fixture=False,
                 dimensions=None, timeout_s=10.0):
        if not isinstance(sensors, dict) or set(sensors) != set(CAMERAS):
            raise ValueError('four original Native sensors required')
        if type(diagnostic_fixture) is not bool:
            raise ValueError('invalid diagnostic flag')
        if dimensions is not None and not diagnostic_fixture:
            raise ValueError('capture profile cannot be overridden for delivery')
        self.dimensions = dimensions or PROFILE
        if set(self.dimensions) != set(CAMERAS) or any(
                not isinstance(size, tuple) or len(size) != 2 or
                any(type(v) is not int or v <= 0 for v in size)
                for size in self.dimensions.values()):
            raise ValueError('invalid camera dimensions')
        self.attempt = Path(attempt)
        self.timeout_s = timeout_s
        self.sensors = sensors
        self.queues = {name: queue.Queue(maxsize=4) for name in CAMERAS}
        self.overflow = set()
        self.processes = {}
        self.media = {}
        self.frames = []
        self.last_frame = None
        self.closed = False
        if any((self.attempt / (name + '.mkv')).exists() for name in CAMERAS):
            raise ValueError('original camera media already exists')
        self.attempt.mkdir(parents=True, exist_ok=True)
        try:
            for name in CAMERAS:
                width, height = self.dimensions[name]
                path = self.attempt / (name + '.mkv')
                self.media[name] = path
                self.processes[name] = subprocess.Popen(
                    ['ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
                     '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size',
                     f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0',
                     '-an', '-c:v', 'ffv1', '-level', '3', str(path)],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE)
                sensors[name].listen(self._callback(name))
        except Exception:
            self.abort()
            raise

    def _callback(self, name):
        def receive(image):
            try:
                self.queues[name].put_nowait(image)
            except queue.Full:
                self.overflow.add(name)
        return receive

    def read(self, frame: int) -> dict:
        if self.closed or type(frame) is not int or frame < 0:
            raise ValueError('invalid Native media readback state')
        if self.last_frame is not None and frame != self.last_frame + 1:
            raise ValueError('Native camera frame sequence differs')
        if self.overflow:
            raise ValueError('original Native camera queue overflow')
        row = {}
        for name in CAMERAS:
            try:
                image = self.queues[name].get(timeout=self.timeout_s)
            except queue.Empty as exc:
                raise ValueError(f'{name} original Native frame missing') from exc
            width, height = self.dimensions[name]
            if (getattr(image, 'frame', None) != frame or
                    getattr(image, 'width', None) != width or
                    getattr(image, 'height', None) != height):
                raise ValueError(f'{name} original Native frame or dimensions differ')
            payload = bytes(image.raw_data)
            if len(payload) != width * height * 4:
                raise ValueError(f'{name} original Native BGRA payload differs')
            process = self.processes[name]
            if process.poll() is not None:
                raise ValueError(f'{name} lossless media writer exited early')
            try:
                process.stdin.write(payload)
            except (BrokenPipeError, OSError) as exc:
                raise ValueError(f'{name} lossless media writer failed') from exc
            row[name] = frame
        self.frames.append({'frame': frame, 'camera_frames': row})
        self.last_frame = frame
        return row

    def finish(self):
        if self.closed:
            raise ValueError('Native media already closed')
        if len(self.frames) != 900:
            raise ValueError('900 original camera frames required')
        try:
            for name in CAMERAS:
                self.processes[name].stdin.close()
            for name in CAMERAS:
                process = self.processes[name]
                error = process.stderr.read().decode('utf-8', errors='replace')
                if process.wait(timeout=120) != 0:
                    raise ValueError(f'{name} lossless media writer failed: {error[:200]}')
                process.stderr.close()
        except Exception:
            self.abort()
            raise
        self.closed = True
        for sensor in self.sensors.values():
            sensor.stop()
        return self.frames, self.media

    def abort(self):
        if self.closed:
            return
        self.closed = True
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except Exception:
                pass
        for process in self.processes.values():
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            if process.stderr:
                process.stderr.close()
