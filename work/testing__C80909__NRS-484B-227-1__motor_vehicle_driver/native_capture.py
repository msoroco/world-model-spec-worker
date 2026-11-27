"""Original CARLA acquisition for a source-reviewed divided-highway U-turn."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from native_driver import (body_polygon, command_next_tick, original_sample,
                           spawn_vehicle, spawn_observed_vehicle)
from divider_construction import spawn_divider, validate_divider
from uturn_control import validate_scene


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def reviewed_context(scene, output, world):
    """Copy independently reviewed context and bind it to the live OpenDRIVE."""
    source = Path(scene["reviewed_context_source"])
    if sha(source) != scene["reviewed_context_sha256"]:
        raise ValueError("reviewed median source hash differs")
    packet = json.loads(source.read_text())
    context = packet["context"]
    if context != scene["context"] or packet.get("divider_props") != scene.get("divider_props"):
        raise ValueError("reviewed median geometry differs from authored scene")
    if sha(Path(scene["authority_review_source"])) != context["authority_review_source_sha256"]:
        raise ValueError("authority review source hash differs")
    live_hash = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
    if live_hash != context["map_source_sha256"]:
        raise ValueError("live OpenDRIVE differs from reviewed map")
    target = Path(output) / "reviewed-median-context.json"
    if target.exists():
        raise ValueError("reviewed median source already retained")
    shutil.copyfile(source, target)
    if sha(target) != scene["reviewed_context_sha256"]:
        raise ValueError("retained reviewed median source changed")
    authority_target = Path(output) / "authority-review-source.json"
    shutil.copyfile(scene["authority_review_source"], authority_target)
    if sha(authority_target) != context["authority_review_source_sha256"]:
        raise ValueError("retained authority review source changed")
    return packet


class CameraBank:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, ego, output, carla, scene):
        self.sensors, self.encoders, self.queues, self.errors = [], {}, {}, []
        self.closed = False
        try:
            self._start(world, ego, Path(output), carla, scene)
        except BaseException:
            self.close()
            raise

    def _start(self, world, ego, output, carla, scene):
        opening = scene["context"]["opening_bounds_xy_m"]
        center = ((opening[0] + opening[2])/2, (opening[1] + opening[3])/2)
        approach = scene["route_xy_m"][0]
        bearing = math.degrees(math.atan2(center[1]-approach[1], center[0]-approach[0]))
        poses = {"overview": (*center, 45, -90, 0),
                 "approach": (*approach, 12, -25, bearing),
                 "reference_corner": (opening[0]-4, opening[1]-4, 12, -35,
                                      math.degrees(math.atan2(center[1]-opening[1]+4,
                                                               center[0]-opening[0]+4))),
                 "driver_reference": (0, 0, 2, 0, 0)}
        library = world.get_blueprint_library()
        for name, width, height in self.SPECS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height), ("fov", 90)):
                bp.set_attribute(key, str(value))
            x, y, z, pitch, yaw = poses[name]
            transform = carla.Transform(carla.Location(x=x,y=y,z=z),
                                        carla.Rotation(pitch=pitch,yaw=yaw))
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
                 "-c:v", "ffv1", "-pix_fmt", "bgra", str(output/(name+".mkv"))],
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
        if errors: raise RuntimeError("; ".join(errors))


def run_native(scene, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import equal, fields

    validate_scene(scene)
    validate_divider(scene)
    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("Native attempt directory must already exist")
    if any((output/name).exists() for name in ("trace.jsonl", "video_frames.jsonl",
                                             "ego-body-history.jsonl", "capture-seal.json")):
        raise ValueError("Native attempt already contains original acquisition")
    if scene["capture_rate_hz"] != 20 or scene["duration_s"] <= 0:
        raise ValueError("synchronous world and camera rate must be 20 Hz")
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    ego = observed_vehicle = cameras = capture = frame_map = None
    divider_actors = []
    frames, phase, error, restored = [], "initializing", None, False
    try:
        packet = reviewed_context(scene, output, world)
        write(output/"acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA live capture with separately reviewed median context",
            "reviewed_context_sha256": sha(output/"reviewed-median-context.json")})
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        divider_actors = spawn_divider(world, scene, carla)
        ego = spawn_vehicle(world, scene, carla)
        observed_vehicle = spawn_observed_vehicle(world, scene, carla)
        context = {**packet["context"], "ego_actor_id": int(ego.id),
                   "observed_vehicle_actor_id": int(observed_vehicle.id),
                   "divider_actor_ids": [int(actor.id) for actor in divider_actors],
                   "reviewed_context_sha256": sha(output/"reviewed-median-context.json")}
        write(output/"median-context.json", context)
        write(output/"divider-geometry.json", {"actors":[
            {"actor_id":int(actor.id),"blueprint_id":item["blueprint_id"],
             "body_vertices_xy_m":body_polygon(actor)}
            for actor,item in zip(divider_actors,scene["divider_props"])]})
        cameras = CameraBank(world, ego, output, carla, scene)
        capture = PipelineCapture(client, ego, output, scene["case_id"])
        frame_map = FrameMap(output/"video_frames.jsonl")
        phase = "capturing"
        state = {}
        count = round(scene["duration_s"]*20)
        with (output/"ego-body-history.jsonl").open("x", buffering=1) as body_stream, \
             (output/"observed-vehicle-history.jsonl").open("x", buffering=1) as observed_stream, \
             (output/"controller-history.jsonl").open("x", buffering=1) as control_stream:
            for _ in range(count):
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise RuntimeError("Native world tick identity differs")
                time_s = snapshot.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                sample = original_sample(ego, snapshot, world.get_map())
                body_stream.write(json.dumps(sample, allow_nan=False)+"\n")
                observed_stream.write(json.dumps(original_sample(observed_vehicle, snapshot, world.get_map()),
                                                 allow_nan=False)+"\n")
                state = command_next_tick(ego, carla, scene, state, sample)
                control_stream.write(json.dumps({"frame": frame, "time_s": time_s,
                    "ego_actor_id": int(ego.id), "next_tick_request": state},
                    allow_nan=False)+"\n")
                frames.append(frame)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ("trace.jsonl", "video_frames.jsonl", "road.xodr", "carla_recorder.log",
                 "reviewed-median-context.json", "authority-review-source.json", "median-context.json",
                 "divider-geometry.json",
                 "ego-body-history.jsonl", "observed-vehicle-history.jsonl",
                 "controller-history.jsonl",
                 *(name+".mkv" for name, *_ in CameraBank.SPECS))
        write(output/"acquisition.json", {name: {"kind": "original_native", "sha256": sha(output/name)}
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
        if ego is not None:
            try: ego.destroy()
            except BaseException as exc: cleanup.append(repr(exc))
        if observed_vehicle is not None:
            try: observed_vehicle.destroy()
            except BaseException as exc: cleanup.append(repr(exc))
        for actor in reversed(divider_actors):
            try: actor.destroy()
            except BaseException as exc: cleanup.append(repr(exc))
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
                context={"opening_id": scene["context"]["opening_id"],
                         "reviewed_context_sha256": sha(output/"reviewed-median-context.json")})
        else:
            write(output/"native-run-status.json", {"phase": phase,
                "errors": [v for v in [error,*cleanup] if v], "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or settings restoration failed")
