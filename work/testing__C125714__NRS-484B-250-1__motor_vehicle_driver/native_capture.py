"""Original Native acquisition for the source-reviewed C125714 crossing.

The capture has no legal evaluator. Context claims require a retained reviewed
packet and a live OpenDRIVE identity match before any actor is spawned.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from native_driver import apply_ego, apply_other, body_polygon, control_step, spawn_vehicles


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def reviewed_context(scene, output, world):
    """Retain a separately inspected packet; never infer legal scope from a route."""
    source = Path(scene["reviewed_context_source"])
    if sha(source) != scene["reviewed_context_sha256"]:
        raise ValueError("reviewed context source hash differs")
    packet = json.loads(source.read_text())
    crossing = scene["crossing"]
    law = packet["law_context"]
    required = ("map_source", "ego_highway", "other_highway", "public_access_source",
                "device_inventory_source", "driver_scope_source", "public_access",
                "human_driver", "devices", "approach_relation", "left_turn_intent",
                "left_turn_realized")
    if any(key not in law for key in required):
        raise ValueError("reviewed law context is incomplete")
    if law["map_source"] != crossing["map_source_sha256"]:
        raise ValueError("reviewed map identity differs from route")
    if (law["ego_highway"], law["other_highway"]) != (
            scene["ego_highway"], scene["other_highway"]):
        raise ValueError("reviewed highway identities differ from route")
    if packet["crossing"] != crossing:
        raise ValueError("reviewed crossing geometry differs from route")
    if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != law["map_source"]:
        raise ValueError("reviewed OpenDRIVE differs from live map")
    if not all(law[key] is True for key in ("public_access", "human_driver")):
        raise ValueError("reviewed public driver scope is unestablished")
    if law["approach_relation"] != "crossing" or law["left_turn_intent"] or law["left_turn_realized"]:
        raise ValueError("reviewed context is outside the crossing branch")
    if law["devices"]:
        raise ValueError("official device exclusion applies to this primary case")
    target = Path(output) / "reviewed-context.json"
    if target.exists():
        raise ValueError("reviewed source already retained")
    shutil.copyfile(source, target)
    if sha(target) != scene["reviewed_context_sha256"]:
        raise ValueError("retained reviewed context changed")
    return packet


class CameraBank:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, ego, output, carla, scene):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        self.closed = False
        try:
            self._start(world, ego, Path(output), carla, scene)
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    def _start(self, world, ego, output, carla, scene):
        library = world.get_blueprint_library()
        bounds = scene["crossing"]["bounds_xy_m"]
        center = ((bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2)
        start = scene["ego_route_xy_m"][0]
        poses = {"overview": (center[0], center[1], 45, -90, 0),
                 "approach": (start[0], start[1], 12, -25,
                              math.degrees(math.atan2(center[1]-start[1], center[0]-start[0]))),
                 "reference_corner": (bounds[0]-4, bounds[1]-4, 12, -35,
                                      math.degrees(math.atan2(center[1]-bounds[1]+4,
                                                               center[0]-bounds[0]+4))),
                 "driver_reference": (0, 0, 2, 0, 0)}
        for name, width, height in self.SPECS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height), ("fov", 90)):
                bp.set_attribute(key, str(value))
            x, y, z, pitch, yaw = poses[name]
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=pitch, yaw=yaw))
            sensor = world.spawn_actor(bp, transform,
                                       attach_to=ego if name == "driver_reference" else None)
            if sensor is None:
                raise RuntimeError("Native camera spawn failed: " + name)
            self.sensors.append(sensor)
            frames = queue.Queue(maxsize=4)
            self.queues[name] = frames
            def receive(image, q=frames, label=name):
                try:
                    q.put_nowait(image)
                except queue.Full:
                    self.errors.append("camera queue overflow: " + label)
            sensor.listen(receive)
            self.encoders[name] = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                 f"{width}x{height}", "-framerate", "20", "-i", "pipe:0", "-an",
                 "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError(name + " camera frame differs from world frame")
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
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
                    errors.append("camera encoder failed: " + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError("; ".join(errors))


def run_native(scene, output, host, port):
    if scene.get("diagnostic_only"):
        raise ValueError("diagnostic scene cannot start Native capture")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import equal, fields

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("Native attempt directory must already exist")
    if scene["capture_rate_hz"] != 20 or scene["duration_s"] <= 0:
        raise ValueError("camera and synchronous world rate must match 20 Hz")
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    actors = {}
    cameras = capture = frame_map = None
    frames = []
    phase = "initializing"
    error = None
    restored = False
    try:
        packet = reviewed_context(scene, output, world)
        write(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA live capture with separately reviewed context",
            "reviewed_context_sha256": sha(output / "reviewed-context.json")})
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        actors = spawn_vehicles(world, scene, carla)
        ego, other = actors["ego"], actors["other"]
        context = {**packet, "ego_actor_id": int(ego.id),
                   "other_actor_id": int(other.id),
                   "reviewed_context_sha256": sha(output / "reviewed-context.json")}
        write(output / "intersection-context.json", context)
        apply_ego(ego, carla, {"request": "brake"})
        cameras = CameraBank(world, ego, output, carla, scene)
        capture = PipelineCapture(client, ego, output, scene["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        phase = "capturing"
        state = {}
        target_index = 1
        count = round(scene["duration_s"] * scene["capture_rate_hz"])
        with (output / "ego-body-history.jsonl").open("x", buffering=1) as ego_stream, \
             (output / "other-body-history.jsonl").open("x", buffering=1) as other_stream, \
             (output / "controller-history.jsonl").open("x", buffering=1) as control_stream:
            for _ in range(count):
                other_request = apply_other(other, carla, scene["other_route_xy_m"],
                                            target_index=target_index)
                target_index = other_request["target_index"]
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise RuntimeError("Native world tick identity differs")
                time_s = snapshot.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                ego_body, other_body = body_polygon(ego), body_polygon(other)
                ego_stream.write(json.dumps({"frame": frame, "time_s": time_s,
                    "actor_id": int(ego.id), "body_vertices_xy_m": ego_body}, allow_nan=False) + "\n")
                other_stream.write(json.dumps({"frame": frame, "time_s": time_s,
                    "actor_id": int(other.id), "body_vertices_xy_m": other_body}, allow_nan=False) + "\n")
                state = control_step(scene, state, frame=frame,
                                     ego_body=ego_body, other_body=other_body)
                apply_ego(ego, carla, state)
                control_stream.write(json.dumps({"frame": frame, "time_s": time_s,
                    "ego_next_tick_request": state, "other_current_tick_request": other_request},
                    allow_nan=False) + "\n")
                frames.append(frame)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ("trace.jsonl", "video_frames.jsonl", "road.xodr", "carla_recorder.log",
                 "reviewed-context.json", "intersection-context.json",
                 "ego-body-history.jsonl", "other-body-history.jsonl",
                 "controller-history.jsonl", *(name + ".mkv" for name, *_ in CameraBank.SPECS))
        write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(output/name)}
                                            for name in names})
        phase = "sealed"
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        cleanup = []
        for resource in (capture, frame_map, cameras):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    cleanup.append(repr(exc))
        for actor in reversed(list(actors.values())):
            try:
                actor.destroy()
            except BaseException as exc:
                cleanup.append(repr(exc))
        try:
            world.apply_settings(original)
            restored = all(equal(fields(world.get_settings()).get(key), value)
                           for key, value in fields(original).items())
        except BaseException as exc:
            cleanup.append(repr(exc))
        if phase == "sealed" and not cleanup and restored:
            seal_capture(output, frames=len(frames), restoration={
                "restored": True,
                "settings_readback": "synchronous_mode and fixed_delta_seconds restored"},
                errors=[], encoder_exit_codes={name: 0 for name, *_ in CameraBank.SPECS},
                context={"crossing_id": scene["crossing"]["crossing_id"],
                         "reviewed_context_sha256": sha(output / "reviewed-context.json")})
        else:
            write(output / "native-run-status.json", {"phase": phase,
                "errors": [value for value in [error, *cleanup] if value],
                "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or settings restoration failed")
