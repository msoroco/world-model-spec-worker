"""Source-gated Native acquisition for C229023 same-lane motorcycle cases.

This module is imported only for an authorized local CARLA execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from scene_review import require

CAMERA_SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def steer_to(actor, point):
    pose = actor.get_transform()
    yaw = math.degrees(math.atan2(point[1] - pose.location.y, point[0] - pose.location.x))
    error = ((yaw - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


class Cameras:
    def __init__(self, world, carla, ego, center, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        poses = ((-20, -15, 28, -55), (-14, -4, 10, -25),
                 (3, -8, 9, -40), (0, 0, 1.55, 0))
        try:
            for (name, width, height), (dx, dy, height_m, pitch) in zip(CAMERA_SPECS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                mounted = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=height_m) if mounted else
                            carla.Location(x=center[0] + dx, y=center[1] + dy, z=height_m))
                sensor = world.spawn_actor(bp, carla.Transform(location, carla.Rotation(pitch=pitch)),
                                           attach_to=ego if mounted else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, slot=frames, label=name):
                    try:
                        slot.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                           "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        require(not self.errors, "; ".join(self.errors))
        for name, _, _ in CAMERA_SPECS:
            image = self.queues[name].get(timeout=15)
            require(image.frame == frame, "camera frame differs from original world frame: " + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        failures = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                failures.append(repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    failures.append("camera encoder failed: " + name)
            except BaseException as error:
                failures.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                failures.append(repr(error))
        self.sensors = []
        self.encoders = {}
        if failures:
            raise RuntimeError("; ".join(failures))


def _station(actor, origin, axis):
    location = actor.get_location()
    return (location.x - origin[0]) * axis[0] + (location.y - origin[1]) * axis[1]


def _sample(actor, role, lane_id, origin, axis):
    pose = actor.get_transform()
    box = actor.bounding_box.extent
    dx, dy = pose.location.x - origin[0], pose.location.y - origin[1]
    return {"actor_id": actor.id, "role": role, "lane_id": lane_id,
            "station_m": dx * axis[0] + dy * axis[1],
            "lateral_m": -dx * axis[1] + dy * axis[0],
            "world_x_m": pose.location.x, "world_y_m": pose.location.y,
            "half_length_m": box.x, "half_width_m": box.y,
            "speed_mps": speed(actor)}


def _controller(actor, carla, route, origin, axis, target_speed):
    station = _station(actor, origin, axis)
    index = min(range(len(route)), key=lambda i: abs(
        (route[i][0] - origin[0]) * axis[0] +
        (route[i][1] - origin[1]) * axis[1] - station - 7))
    actual = speed(actor)
    actor.apply_control(carla.VehicleControl(
        throttle=0.26 if actual < target_speed - 0.3 else 0,
        brake=0.20 if actual > target_speed + 0.5 else 0,
        steer=steer_to(actor, route[index])))


def run_native(cfg, scene_path, request, output, host, port):
    """Capture one original episode and close every owned resource in order."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    require(output.is_dir(), "Native attempt directory must already exist")
    scene_path = Path(scene_path).resolve()
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    actors = {}
    cameras = capture = frame_map = None
    phase, errors, restored = "initializing", [], False
    rows = []
    try:
        archive = output / "reviewed-scene-packet"
        archive.mkdir(exist_ok=False)
        shutil.copy2(scene_path, archive / "scene.json")
        for item in scene["sources"].values():
            source = (scene_path.parent / item["path"]).resolve()
            target = archive / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        require(world.get_map().name == scene["map_id"], "reviewed Native map ID differs")
        digest = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        require(digest == scene["opendrive_sha256"], "reviewed original map bytes differ")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        yaw = math.degrees(math.atan2(request["route_unit_xy"][1],
                                      request["route_unit_xy"][0]))
        shift = cfg.get("engineering", {}).get("start_station_shift_m", 0)
        require(shift in (0, -3), "unreviewed engineering start shift")
        blueprint_ids = {"ego": scene["ego_blueprint_id"],
                         "other": scene["other_blueprint_id"],
                         "third": scene.get("third_blueprint_id")}
        for item in request["participants"]:
            role = item["role"]
            blueprint_id = blueprint_ids[role]
            require(blueprint_id, "reviewed participant blueprint missing: " + role)
            blueprint = world.get_blueprint_library().find(blueprint_id)
            shifted_x = item["xy"][0] + shift * request["route_unit_xy"][0]
            shifted_y = item["xy"][1] + shift * request["route_unit_xy"][1]
            pose = carla.Transform(carla.Location(x=shifted_x, y=shifted_y,
                                                  z=scene["survey"]["spawn_z_m"]),
                                   carla.Rotation(yaw=yaw))
            waypoint = world.get_map().get_waypoint(pose.location, project_to_road=False)
            require(waypoint is not None and waypoint.lane_id == item["lane_id"],
                    "reviewed Native spawn lane differs: " + role)
            actor = world.try_spawn_actor(blueprint, pose)
            require(actor is not None and actor.type_id == blueprint_id,
                    "reviewed Native participant spawn failed: " + role)
            actors[role] = actor
        write(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA source-gated motorcycle pass or abreast run"})
        midpoint = request["routes"]["ego"][len(request["routes"]["ego"]) // 2]
        cameras = Cameras(world, carla, actors["ego"], midpoint, output)
        capture = PipelineCapture(client, actors["ego"], output,
                                  cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        origin, axis = request["route_origin_xy"], request["route_unit_xy"]
        phase = "capturing"
        with (output / "same-lane-history.jsonl").open("x", buffering=1) as stream:
            for _ in range(round(cfg["duration_s"] * cfg["rate_hz"])):
                for role, actor in actors.items():
                    target = (8.0 if cfg["case"]["requested_pass"] and role == "ego"
                              else 4.0 if cfg["case"]["requested_pass"] else 5.0)
                    _controller(actor, carla, request["routes"][role], origin, axis,
                                target)
                frame = world.tick()
                snap = world.get_snapshot()
                require(snap.frame == frame, "original Native frame identity changed")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                observed = {}
                for role, actor in actors.items():
                    waypoint = world.get_map().get_waypoint(
                        actor.get_location(), project_to_road=False)
                    require(waypoint is not None, "participant left reviewed drivable map")
                    observed[role] = _sample(actor, role, waypoint.lane_id,
                                             origin, axis)
                row = {"frame": frame, "time_s": time_s,
                       "actors": observed,
                       "scene_source_sha256": sha(scene_path)}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        scene["participant_readback"] = {role: {"actor_id": actor.id}
                                          for role, actor in actors.items()}
        write(output / "same-lane-scene.json", scene)
        names = ["trace.jsonl", "video_frames.jsonl", "same-lane-history.jsonl",
                 "same-lane-scene.json", "road.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, _, _ in CAMERA_SPECS]]
        names.extend(str(p.relative_to(output)) for p in archive.rglob("*")
                     if p.is_file())
        write(output / "acquisition.json", {
            name: {"kind": "original_native", "sha256": sha(output / name)}
            for name in names})
        phase = "sealed"
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (capture, frame_map, cameras):
            if resource:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        for actor in reversed(list(actors.values())):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            restored = restore(client, saved_world)["restored"]
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={"restored": True,
                                      "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in CAMERA_SPECS},
                         context={"same_lane_case": cfg["selected_case_id"]})
        else:
            write(output / "native-run-status.json", {
                "phase": phase, "errors": errors,
                "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
