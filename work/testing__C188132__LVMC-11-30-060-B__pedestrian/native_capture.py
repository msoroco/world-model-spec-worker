"""Lazy, original CARLA pedestrian and four-camera frame acquisition checks.

The caller owns CARLA world setup, media encoding, and attempt sealing. These
checks run before an acquired frame is accepted as source evidence.
"""
from __future__ import annotations

import math
import queue
import subprocess
from pathlib import Path



CAMERA_SPECS = {"overview": (1920, 1080), "approach": (1280, 720),
                "reference_corner": (1280, 720),
                "driver_reference": (1280, 720)}


def camera_placements(scene):
    """Four fixed original views of the surface crossing and elevated deck."""
    if scene.get("crossing_point_xy_m") != [0.0, 0.0]:
        raise ValueError("crossing point differs from overpass camera plan")
    sites = {"overview": (-18.0, -15.0, 22.0),
             "approach": (-12.0, -3.0, 4.0),
             "reference_corner": (8.0, 11.0, 10.0),
             "driver_reference": (-8.0, -2.0, 2.2)}
    target = (0.0, 0.0, 2.5)
    placements = {}
    for name, location in sites.items():
        dx, dy, dz = (target[i]-location[i] for i in range(3))
        yaw = math.degrees(math.atan2(dy, dx))
        pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        placements[name] = {"location_xyz_m": location,
                            "rotation_pitch_yaw_deg": (pitch, yaw),
                            "target_xyz_m": target}
    return placements


def spawn_native_cameras(world, scene, carla):
    """Construct four RGB sensors; destroy partial spawns on any failure."""
    placements = camera_placements(scene)
    sensors = {}
    try:
        for name, (width, height) in CAMERA_SPECS.items():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            if blueprint is None:
                raise ValueError("Native RGB camera blueprint missing")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 90)):
                blueprint.set_attribute(key, str(value))
            placement = placements[name]
            x, y, z = placement["location_xyz_m"]
            pitch, yaw = placement["rotation_pitch_yaw_deg"]
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=pitch, yaw=yaw))
            sensor = world.spawn_actor(blueprint, transform)
            if sensor is None:
                raise ValueError(name+" Native camera spawn failed")
            sensors[name] = sensor
        return sensors
    except BaseException:
        for sensor in reversed(list(sensors.values())):
            sensor.destroy()
        raise


def sample_original_walker(scene, actor, snapshot):
    """Read the actor's world-space bounding box, not its commanded route."""
    frame = int(snapshot.frame)
    time_s = float(snapshot.timestamp.elapsed_seconds)
    if frame < 0 or not math.isfinite(time_s):
        raise ValueError("invalid original world frame or timestamp")
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) != 8:
        raise ValueError("original walker needs eight world-space body vertices")
    xyz = [(float(v.x), float(v.y), float(v.z)) for v in vertices]
    if not all(math.isfinite(v) for point in xyz for v in point):
        raise ValueError("nonfinite original walker body")
    xs = [point[0] for point in xyz]
    ys = [point[1] for point in xyz]
    if max(xs)-min(xs) < .1 or max(ys)-min(ys) < .1:
        raise ValueError("degenerate original walker footprint")
    body = [[min(xs), min(ys)], [max(xs), min(ys)],
            [max(xs), max(ys)], [min(xs), max(ys)]]
    return {"case_id": scene["case_id"], "actor_id": int(actor.id),
            "frame": frame, "time_s": time_s, "body_xy_m": body,
            "body_z_min_m": min(point[2] for point in xyz),
            "body_z_max_m": max(point[2] for point in xyz),
            "source_kind": "original_native_world_vertices"}


class FourViewJoin:
    """Reject incomplete, stale or malformed camera frames before encoding."""

    def __init__(self):
        self.previous_frame = None
        self.previous_time_s = None

    def append(self, walker_sample, images):
        frame = walker_sample["frame"]
        time_s = walker_sample["time_s"]
        if self.previous_frame is not None:
            if frame != self.previous_frame+1:
                raise ValueError("original world frames are not consecutive")
            if abs(time_s-self.previous_time_s-.05) > .005:
                raise ValueError("original world frame timing is not 20 Hz")
        if set(images) != set(CAMERA_SPECS):
            raise ValueError("four named original camera views required")
        receipt = {"case_id": walker_sample["case_id"], "frame": frame,
                   "time_s": time_s, "walker_actor_id": walker_sample["actor_id"],
                   "cameras": {}}
        for name, (width, height) in CAMERA_SPECS.items():
            image = images[name]
            if (int(image.frame) != frame or int(image.width) != width or
                    int(image.height) != height or len(image.raw_data) != width*height*4):
                raise ValueError(name+" original camera frame, resolution or BGRA size differs")
            receipt["cameras"][name] = {"frame": frame, "width": width,
                                        "height": height, "pixel_format": "bgra",
                                        "bytes": width*height*4}
        self.previous_frame = frame
        self.previous_time_s = time_s
        return receipt


class FourVideoRecorder:
    """Acquire four synchronized original BGRA streams into lossless videos.

    A failed frame leaves the attempt incomplete. The caller must seal only after
    `close` succeeds and an independent decoder checks every resulting video.
    """

    def __init__(self, world, scene, carla, output, encoder_factory=None):
        self.output = Path(output)
        if not self.output.is_dir():
            raise ValueError("fresh existing Native attempt directory required")
        if any((self.output/(name+".mkv")).exists() for name in CAMERA_SPECS):
            raise ValueError("Native video outputs already exist")
        self.join = FourViewJoin()
        self.queues = {}
        self.sensors = {}
        self.encoders = {}
        self.errors = []
        self.closed = False
        encoder_factory = encoder_factory or subprocess.Popen
        try:
            self.sensors = spawn_native_cameras(world, scene, carla)
            for name, (width, height) in CAMERA_SPECS.items():
                inbox = queue.Queue(maxsize=4)
                self.queues[name] = inbox

                def receive(image, target=inbox, label=name):
                    try:
                        target.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: "+label)

                self.sensors[name].listen(receive)
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                           "-n", "-f", "rawvideo", "-pixel_format", "bgra",
                           "-video_size", f"{width}x{height}", "-framerate", "20",
                           "-i", "pipe:0", "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                           str(self.output/(name+".mkv"))]
                self.encoders[name] = encoder_factory(
                    command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, walker_sample):
        if self.closed:
            raise ValueError("Native video recorder already closed")
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        images = {name: self.queues[name].get(timeout=15) for name in CAMERA_SPECS}
        receipt = self.join.append(walker_sample, images)
        for name, image in images.items():
            written = self.encoders[name].stdin.write(image.raw_data)
            if written != len(image.raw_data):
                raise RuntimeError(name+" encoder wrote incomplete original frame")
        return receipt

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(list(self.sensors.values())):
            try: sensor.stop()
            except BaseException as exc: errors.append("sensor stop: "+repr(exc))
        for name, encoder in self.encoders.items():
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    errors.append(name+" encoder failed")
            except BaseException as exc:
                errors.append(name+" encoder close: "+repr(exc))
        for sensor in reversed(list(self.sensors.values())):
            try: sensor.destroy()
            except BaseException as exc: errors.append("sensor destroy: "+repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
