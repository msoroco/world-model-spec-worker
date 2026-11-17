"""Retain four synchronized original RGB camera streams as FFV1 media."""
from pathlib import Path
import queue
import subprocess

import numpy as np

from native_scene import VIEWS


class CameraRecorder:
    def __init__(self, output, cameras, specs):
        self.output = Path(output)
        if set(cameras) != set(VIEWS) or set(specs) != set(VIEWS):
            raise ValueError('All four named source cameras are required')
        self.queues = {}
        self.processes = {}
        self.logs = {}
        self.specs = specs
        self.previous_frame = None
        self.closed = False
        self.output.mkdir(parents=True, exist_ok=True)
        try:
            for name in VIEWS:
                width, height = specs[name]
                if type(width) is not int or type(height) is not int or min(width, height) < 8:
                    raise ValueError('Invalid source-camera dimensions')
                path = self.output / (name + '.mkv')
                if path.exists():
                    raise ValueError('Retain existing source camera media')
                self.queues[name] = queue.Queue(maxsize=8)
                self.logs[name] = (self.output / (name + '.encoder.log')).open('x')
                command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', f'{width}x{height}', '-r', '20', '-i', 'pipe:0',
                           '-an', '-c:v', 'ffv1', '-level', '1', str(path)]
                self.processes[name] = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stderr=self.logs[name])
                cameras[name].listen(self.queues[name].put)
        except BaseException:
            self.close(check=False)
            raise

    def capture(self, frame, timeout_s=30):
        if self.closed:
            raise ValueError('Camera recorder is closed')
        if type(frame) is not int or frame < 0 or (
                self.previous_frame is not None and frame <= self.previous_frame):
            raise ValueError('Native camera frames must increase')
        for name in VIEWS:
            image = self.queues[name].get(timeout=timeout_s)
            width, height = self.specs[name]
            if image.frame != frame or image.width != width or image.height != height:
                raise ValueError('Camera source frame or dimensions differ from Native tick')
            raw = np.frombuffer(image.raw_data, dtype=np.uint8)
            if raw.size != width * height * 4:
                raise ValueError('Camera source lacks BGRA pixels')
            rgb = raw.reshape(height, width, 4)[:, :, 2::-1].tobytes()
            self.processes[name].stdin.write(rgb)
        self.previous_frame = frame

    def close(self, *, check=True):
        if self.closed:
            return {}
        self.closed = True
        codes = {}
        for name, process in self.processes.items():
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                codes[name] = process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                codes[name] = process.wait()
            self.logs[name].close()
        if check and (set(codes) != set(VIEWS) or any(code != 0 for code in codes.values())):
            raise ValueError('Four source-camera encoders did not close cleanly')
        return codes
