"""Original Native capture of a red-X bus attempt; no CARLA import on CPU."""
from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
from pathlib import Path

from native_driver import apply_request, spawn_scene


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
RATE_HZ = 20


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False, indent=2) + "\n")


class CameraCapture:
    def __init__(self, world, bus, scene, output, carla):
        self.sensors, self.encoders, self.queues = [], {}, {}
        self.closed = False
        try:
            self._start(world, bus, scene, output, carla)
        except BaseException:
            self.close()
            raise

    def _start(self, world, bus, scene, output, carla):
        poses = {"overview": (35, -3.6, 18), "approach": (34, -5.4, 5),
                 "reference_corner": (50, -1.8, 8), "driver_reference": (0, 0, 3)}
        for name in CAMERAS:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            if bp is None:
                raise ValueError("original RGB camera blueprint missing")
            width, height = (1920, 1080) if name == "overview" else (1280, 720)
            for attr, value in (("image_size_x", width), ("image_size_y", height), ("fov", 90)):
                bp.set_attribute(attr, str(value))
            x, y, z = poses[name]
            attached = bus if name == "driver_reference" else None
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(yaw=0.0 if attached else 180.0))
            sensor = world.spawn_actor(bp, transform, attach_to=attached) if attached else world.spawn_actor(bp, transform)
            if sensor is None:
                raise RuntimeError("original camera spawn failed: " + name)
            self.sensors.append(sensor)
            frames = queue.Queue(maxsize=8)
            self.queues[name] = frames
            sensor.listen(lambda image, q=frames: q.put_nowait(image))
            process = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
                "-framerate", str(RATE_HZ), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                "-pix_fmt", "bgra", str(Path(output) / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.encoders[name] = process

    def append(self, frame):
        for name in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera/world frame mismatch: " + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try: sensor.stop()
            except BaseException as exc: errors.append(repr(exc))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed: process.stdin.close()
                if process.wait(timeout=180) != 0: errors.append("camera encoder failed: " + name)
            except BaseException as exc: errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try: sensor.destroy()
            except BaseException as exc: errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


def _footprint(bus):
    vertices = bus.bounding_box.get_world_vertices(bus.get_transform())
    if len(vertices) == 8 and all(hasattr(vertex, "z") for vertex in vertices):
        vertices = sorted(vertices, key=lambda vertex: vertex.z)[:4]
    points = {(float(v.x), float(v.y)) for v in vertices}
    if len(points) < 3 or any(not math.isfinite(value) for point in points for value in point):
        raise ValueError("observed bus footprint lacks finite planar vertices")
    ordered = sorted(points)

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    if len(hull) != 4:
        raise ValueError("observed bus footprint is not a four-corner body")
    return [list(point) for point in hull]


def _retain_review(packet_path, output):
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    for key in ("highway", "official_device"):
        rel = Path(packet[key]["source_path"])
        source = packet_path.parent / rel
        target = output / rel
        if target.exists() or not source.is_file():
            raise ValueError("review source missing or collides with attempt file")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(packet_path, output / "reviewed-context.json")


def run_native(scene, road, site, output, host, port, packet_path):
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(scratch / "c147332-native-runtime")
    if not Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().is_relative_to(scratch):
        raise ValueError("pipeline output root must remain under .runtime-work")
    output = Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(scratch):
        raise ValueError("fresh materialized attempt under .runtime-work required")
    if (output / "capture-seal.json").exists():
        raise ValueError("attempt already sealed")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields, equal

    client = carla.Client(host, port)
    client.set_timeout(30)
    original_world = client.get_world()
    original_map = original_world.get_map().name
    if not original_map or original_map.startswith("OpenDriveMap"):
        raise ValueError("restorable original map required")
    original_settings = original_world.get_settings()
    world = None
    actors = []
    cameras = capture = frame_map = None
    frames = []
    phase = "initializing"
    restored = False
    error = None
    try:
        if _sha(road) != scene["map_source_sha256"]:
            raise ValueError("authored map changed before Native import")
        _retain_review(packet_path, output)
        shutil.copy2(road, output / "authored-road.xodr")
        world = client.generate_opendrive_world(Path(road).read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        bus, head = spawn_scene(world, scene, carla, site)
        actors.extend((bus, head))
        cameras = CameraCapture(world, bus, scene, output, carla)
        capture = PipelineCapture(client, bus, output, scene["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        phase = "capturing"
        with (output / "bus-body-history.jsonl").open("x", buffering=1) as body_file, \
             (output / "lane-signal-history.jsonl").open("x", buffering=1) as signal_file, \
             (output / "sign-state-original.jsonl").open("x", buffering=1) as head_file, \
             (output / "camera-frame-map.jsonl").open("x", buffering=1) as camera_file, \
             (output / "controller-history.jsonl").open("x", buffering=1) as control_file:
            for index in range(round(scene["capture_plan"]["duration_s"] * RATE_HZ)):
                request = apply_request(bus, scene, carla)
                frame = world.tick()
                snapshot = world.get_snapshot()
                if frame != snapshot.frame:
                    raise RuntimeError("Native world frame mismatch")
                time_s = snapshot.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                common = {"frame": frame, "elapsed_seconds": time_s}
                body_file.write(json.dumps({**common, "source_path": "trace.jsonl",
                    "bus_actor_id": int(bus.id), "bus_footprint": _footprint(bus)}, allow_nan=False) + "\n")
                signal_file.write(json.dumps({**common, "source_path": "sign-state-original.jsonl",
                    "governed_lane_id": "red_lane", "lane_lateral_bounds_m": [-3.6, 0.0],
                    "symbol": "red_x", "faces_bus": True,
                    "official_device_source_sha256": site["official_device_source_sha256"]}, allow_nan=False) + "\n")
                head_file.write(json.dumps({**common, "head_actor_id": int(head.id),
                    "head_blueprint_id": site["native_asset_blueprint_id"],
                    "head_position": [head.get_transform().location.x,
                                      head.get_transform().location.y,
                                      head.get_transform().location.z]}, allow_nan=False) + "\n")
                camera_file.write(json.dumps({**common, "source_path": "video_frames.jsonl",
                    "camera_names": list(CAMERAS)}, allow_nan=False) + "\n")
                control_file.write(json.dumps({**common, "requested_control": request}, allow_nan=False) + "\n")
                frames.append(frame)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ["reviewed-context.json", "authored-road.xodr", "road.xodr", "trace.jsonl",
                 "video_frames.jsonl", "carla_recorder.log", "bus-body-history.jsonl",
                 "lane-signal-history.jsonl", "sign-state-original.jsonl",
                 "camera-frame-map.jsonl", "controller-history.jsonl",
                 *(name + ".mkv" for name in CAMERAS)]
        packet = json.loads((output / "reviewed-context.json").read_text())
        names.extend(packet[key]["source_path"] for key in ("highway", "official_device"))
        _write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": _sha(output / name)}
                                             for name in names})
        phase = "sealed"
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        cleanup = []
        for resource in (capture, frame_map, cameras):
            if resource is not None:
                try: resource.close()
                except BaseException as exc: cleanup.append(repr(exc))
        for actor in reversed(actors):
            try: actor.destroy()
            except BaseException as exc: cleanup.append(repr(exc))
        try:
            restored_world = client.load_world(original_map)
            restored_world.apply_settings(original_settings)
            restored = restored_world.get_map().name == original_map and all(
                equal(fields(restored_world.get_settings()).get(k), value)
                for k, value in fields(original_settings).items())
        except BaseException as exc:
            cleanup.append(repr(exc))
        if phase == "sealed" and not cleanup and restored:
            seal_capture(output, frames=len(frames), restoration={
                "restored": True, "settings_readback": "original map and settings restored"},
                errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                context={"case_id": scene["case_id"],
                         "authored_road_sha256": _sha(output / "authored-road.xodr"),
                         "reviewed_packet_sha256": site["reviewed_packet_sha256"]})
        else:
            _write(output / "native-run-status.json", {"phase": phase,
                "errors": [e for e in [error, *cleanup] if e],
                "original_world_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or original world restoration failed")
