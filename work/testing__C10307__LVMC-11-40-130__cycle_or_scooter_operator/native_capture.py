"""Four original RGB cameras synchronized to PipelineCapture's single run.

No simulator is contacted on import. The caller owns the world and its restore.
"""
from __future__ import annotations
import json
import queue
import subprocess
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
POSITIONS = {
    "overview": ((0.0, 0.0, 48.0), (-90.0, 0.0, 0.0)),
    "approach": ((-35.0, -0.75, 4.0), (-9.0, 0.0, 0.0)),
    "reference_corner": ((0.0, 10.0, 6.0), (-20.0, -90.0, 0.0)),
    "driver_reference": ((-34.0, -0.75, 2.0), (-5.0, 0.0, 0.0)),
}


def camera_transform(carla, name):
    position, angles = POSITIONS[name]
    return carla.Transform(carla.Location(x=position[0], y=position[1], z=position[2]),
                           carla.Rotation(pitch=angles[0], yaw=angles[1], roll=angles[2]))


class FrameJoin:
    """Require every live RGB packet on the one original frame/time axis."""
    def __init__(self):
        self.previous = None
        self.count = 0

    def accept(self, frame, time_s, images):
        if set(images) != set(CAMERAS) or any(int(image.frame) != frame for image in images.values()):
            raise ValueError("four live RGB sources do not match original frame")
        if self.previous is not None:
            old_frame, old_time = self.previous
            if frame != old_frame + 1 or not 0.045 <= time_s - old_time <= 0.055:
                raise ValueError("original RGB frame/time discontinuity")
        row = {"video_frame": self.count, "carla_frame": frame,
               "native_frame": frame, "time_s": time_s}
        self.previous = frame, time_s
        self.count += 1
        return row


class FourCameraCapture:
    """Stream BGRA Native pixels to four lossless FFV1 sources, with cleanup."""
    def __init__(self, world, carla, config, output):
        self.output = Path(output)
        self.queues = {}
        self.sensors = []
        self.encoders = []
        self.errors = []
        self.join = FrameJoin()
        self.mapping = (self.output / "video_frames.jsonl").open("x", buffering=1)
        try:
            library = world.get_blueprint_library()
            for item in config["cameras"]:
                name = item["name"]
                if name not in CAMERAS or name in self.queues:
                    raise ValueError("invalid original RGB camera contract")
                bp = library.find("sensor.camera.rgb")
                for key, value in (("image_size_x", item["width"]), ("image_size_y", item["height"]),
                                   ("fov", item["fov_deg"]), ("sensor_tick", 0)):
                    bp.set_attribute(key, str(value))
                sensor = world.spawn_actor(bp, camera_transform(carla, name))
                if sensor is None:
                    raise RuntimeError("Native RGB sensor spawn failed: " + name)
                self.sensors.append(sensor)
                if int(sensor.attributes["image_size_x"]) != item["width"] or int(sensor.attributes["image_size_y"]) != item["height"]:
                    raise ValueError("Native RGB sensor dimensions differ from capture plan")
                inbox = queue.Queue(maxsize=4)
                self.queues[name] = (inbox, item)
                def receive(image, *, inbox=inbox, name=name):
                    try:
                        inbox.put_nowait(image)
                    except queue.Full:
                        self.errors.append("Native RGB queue overflow: " + name)
                sensor.listen(receive)
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f'{item["width"]}x{item["height"]}',
                           "-r", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1", "-threads", "1",
                           "-fflags", "+bitexact", "-flags:v", "+bitexact", str(self.output / (name + ".mkv"))]
                stderr_file = (self.output / (name + "-encoder.log")).open("w")
                try:
                    encoder = subprocess.Popen(command, stdin=subprocess.PIPE,
                                               stdout=subprocess.DEVNULL, stderr=stderr_file)
                except BaseException:
                    stderr_file.close()
                    raise
                self.encoders.append((name, encoder, stderr_file))
            if set(self.queues) != set(CAMERAS):
                raise ValueError("four original RGB cameras required")
        except BaseException:
            self.close(require_frames=False)
            raise

    def capture(self, frame, time_s):
        if self.errors:
            raise RuntimeError(self.errors[0])
        images = {name: inbox.get(timeout=15) for name, (inbox, _) in self.queues.items()}
        row = self.join.accept(frame, time_s, images)
        for name, image in images.items():
            expected = self.queues[name][1]["width"] * self.queues[name][1]["height"] * 4
            if len(image.raw_data) != expected:
                raise ValueError("Native RGB byte count differs from configured dimensions")
        for name, encoder, _ in self.encoders:
            encoder.stdin.write(bytes(images[name].raw_data))
        self.mapping.write(json.dumps(row) + "\n")
        return row

    def close(self, require_frames=True):
        if not self.mapping.closed:
            self.mapping.close()
        for sensor in reversed(self.sensors):
            sensor.stop()
            sensor.destroy()
        for name, encoder, stderr_file in self.encoders:
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                exit_code = encoder.wait(timeout=120)
            finally:
                stderr_file.close()
            if require_frames and exit_code:
                raise RuntimeError("FFV1 encoder failed: " + name)
        if require_frames and self.join.count == 0:
            raise ValueError("no original RGB frames recorded")
        return self.join.count
