"""Four frame-joined original CARLA views for a source-reviewed sight site."""
from __future__ import annotations

import queue
import math
import subprocess
from pathlib import Path


SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


class NativeSightCameras:
    def __init__(self, world, site: dict, output: Path, carla, encoder_factory=None):
        self.output = Path(output)
        if not self.output.is_dir():
            raise ValueError("camera scratch directory required")
        self.sensors, self.encoders, self.queues, self.errors = [], {}, {}, []
        self.closed = False
        mounts = site.get("camera_mounts")
        if not isinstance(mounts, dict) or set(mounts) != {name for name, _, _ in SPECS}:
            raise ValueError("four reviewed camera mounts required")
        self.encoder_factory = encoder_factory or subprocess.Popen
        try:
            for name, width, height in SPECS:
                mount = mounts[name]
                if (not isinstance(mount, dict) or
                        set(mount) != {"x", "y", "z", "pitch", "yaw", "roll", "fov"} or
                        any(type(mount[k]) not in (int, float) or
                            not math.isfinite(mount[k]) for k in mount) or
                        not 30 <= mount["fov"] <= 120):
                    raise ValueError("incomplete reviewed camera mount: " + name)
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                if bp is None:
                    raise ValueError("Native RGB camera blueprint missing")
                for key, value in (("image_size_x", width), ("image_size_y", height),
                                   ("fov", mount["fov"],)):
                    bp.set_attribute(key, str(value))
                transform = carla.Transform(
                    carla.Location(x=mount["x"], y=mount["y"], z=mount["z"]),
                    carla.Rotation(pitch=mount["pitch"], yaw=mount["yaw"], roll=mount["roll"]))
                sensor = world.spawn_actor(bp, transform)
                if sensor is None:
                    raise RuntimeError("Native camera spawn failed: " + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, frame_queue=frames, label=name):
                    try:
                        frame_queue.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera overflow: " + label)

                sensor.listen(receive)
                self.encoders[name] = self.encoder_factory(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                     "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                     f"{width}x{height}", "-framerate", "20", "-i", "pipe:0", "-an",
                     "-c:v", "ffv1", "-pix_fmt", "bgra", str(self.output / (name + ".mkv"))],
                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame: int) -> None:
        if self.closed:
            raise RuntimeError("camera recorder closed")
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, width, height in SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError(name + " camera/world frame mismatch")
            if len(image.raw_data) != width * height * 4:
                raise RuntimeError(name + " camera raw frame size mismatch")
            self.encoders[name].stdin.write(image.raw_data)

    def close(self) -> None:
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
                    errors.append("encoder failed: " + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))

    def files(self) -> dict[str, Path]:
        if not self.closed:
            raise ValueError("camera encoders must close before sealing")
        files = {name: self.output / (name + ".mkv") for name, _, _ in SPECS}
        if any(not path.is_file() or path.stat().st_size == 0 for path in files.values()):
            raise ValueError("four original camera videos required")
        return files
