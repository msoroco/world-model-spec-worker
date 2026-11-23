"""Four original RGB camera streams for a private C227824 Native attempt.

The caller supplies four already placed CARLA sensors. Source-reviewed camera
placement and independent decode/sealing remain separate requirements.
"""
from __future__ import annotations

import queue
import subprocess
from pathlib import Path

from saved_entry import CAMERAS


SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class FourStreamRecorder:
    """Own four sensor subscriptions and encoders; fail closed on lost frames."""

    def __init__(self, sensors, output, encoder_factory=None):
        if not isinstance(sensors, dict) or set(sensors) != set(CAMERAS):
            raise ValueError("four named original RGB sensors required")
        self.output = Path(output).resolve()
        if not self.output.is_dir() or any((self.output / (name + ".mkv")).exists() for name in CAMERAS):
            raise ValueError("fresh Native video output directory required")
        self.sensors = sensors
        self.queues = {name: queue.Queue(maxsize=4) for name in CAMERAS}
        self.encoders = {}
        self.errors = []
        self.closed = False
        self.count = 0
        encoder_factory = encoder_factory or subprocess.Popen
        try:
            for name in CAMERAS:
                inbox = self.queues[name]

                def receive(image, target=inbox, label=name):
                    try:
                        target.put_nowait(image)
                    except queue.Full:
                        self.errors.append("original camera queue overflow: " + label)

                sensors[name].listen(receive)
                width, height = SIZES[name]
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                           "-n", "-f", "rawvideo", "-pixel_format", "bgra",
                           "-video_size", f"{width}x{height}", "-framerate", "20",
                           "-i", "pipe:0", "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                           str(self.output / (name + ".mkv"))]
                self.encoders[name] = encoder_factory(
                    command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def capture(self, frame):
        if self.closed or self.errors:
            raise RuntimeError("closed or failed original camera recorder: " + "; ".join(self.errors))
        images = {}
        for name in CAMERAS:
            try:
                image = self.queues[name].get(timeout=15)
            except queue.Empty as exc:
                raise RuntimeError("missing original camera frame: " + name) from exc
            width, height = SIZES[name]
            if (image.frame != frame or image.width != width or image.height != height
                    or len(image.raw_data) != width * height * 4):
                raise ValueError("stale or invalid original camera frame: " + name)
            images[name] = image
        return images

    def append(self, images):
        if self.closed or self.errors or set(images) != set(CAMERAS):
            raise ValueError("incomplete original camera group")
        for name in CAMERAS:
            image = images[name]
            width, height = SIZES[name]
            if image.width != width or image.height != height or len(image.raw_data) != width * height * 4:
                raise ValueError("invalid original camera bytes: " + name)
        for name in CAMERAS:
            data = images[name].raw_data
            if self.encoders[name].stdin.write(data) != len(data):
                raise RuntimeError("incomplete original video write: " + name)
        self.count += 1

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except BaseException as exc:
                errors.append("camera stop: " + repr(exc))
        for name, encoder in self.encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    errors.append("original encoder failed: " + name)
            except BaseException as exc:
                errors.append("original encoder close: " + repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
