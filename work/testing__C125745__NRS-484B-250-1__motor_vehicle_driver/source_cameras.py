"""Four original Native RGB sources with exact frame joins and lossless closure."""

from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Queue
import subprocess


CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def matching_frame(queue, frame, timeout_s=10):
    """Reject a skipped Native tick; discard only older buffered frames."""
    for _ in range(8):
        try:
            image = queue.get(timeout=timeout_s)
        except Empty as exc:
            raise ValueError("Missing Native source-camera frame: " + str(frame)) from exc
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError("Source camera skipped Native frame: " + str(frame))
    raise ValueError("Source camera failed exact Native frame join")


@contextmanager
def source_cameras(world, ego, transforms):
    """Own four sensors and their frame queues; require the reviewed camera plan."""
    if not isinstance(transforms, dict) or set(transforms) != set(CAMERAS):
        raise ValueError("Four named Native source-camera transforms required")
    sensors = []
    queues = {}
    try:
        for name, (width, height) in CAMERAS.items():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            if blueprint is None:
                raise ValueError("Native RGB source blueprint missing")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 90), ("sensor_tick", .05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {"attach_to": ego} if name == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError("Native source-camera spawn failed: " + name)
            queue = Queue()
            sensor.listen(queue.put)
            sensors.append(sensor)
            queues[name] = queue
        yield queues
    finally:
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()


class SourceVideo:
    """Write original BGRA bytes as a lossless 20 Hz FFV1 source stream."""

    def __init__(self, path, width, height):
        self.path = Path(path)
        if self.path.exists() or width <= 0 or height <= 0:
            raise ValueError("Fresh source-video path and positive dimensions required")
        self.width, self.height, self.frames = width, height, 0
        self.process = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
             "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
             f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
             "-an", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0",
             str(self.path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.closed = False

    def write(self, image, frame):
        if self.closed or image.frame != frame:
            raise ValueError("Original source frame differs from Native tick")
        data = image.raw_data
        if not isinstance(data, (bytes, bytearray)) or len(data) != self.width * self.height * 4:
            raise ValueError("Original BGRA source dimensions differ")
        if self.process.poll() is not None:
            raise ValueError("Source encoder exited before frame closure")
        self.process.stdin.write(data)
        self.frames += 1

    def close(self):
        if self.closed:
            raise ValueError("Source-video owner already released")
        self.closed = True
        self.process.stdin.close()
        code = self.process.wait(timeout=60)
        error = self.process.stderr.read().decode(errors="replace")
        self.process.stderr.close()
        if code != 0 or self.frames == 0 or not self.path.is_file():
            raise ValueError("Source encoder failed: " + error[-1000:])
        return {"path": str(self.path), "frames": self.frames,
                "width": self.width, "height": self.height,
                "fps": 20, "encoding": "ffv1-lossless"}
