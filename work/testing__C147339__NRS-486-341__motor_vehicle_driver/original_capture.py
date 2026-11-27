"""Source-gated 20 Hz Native capture for original protected-lane measurements.

The reviewed packet supplies map bytes, routes and classifications. This code
does not infer those facts from a blueprint name or synthetic fixture.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from lane_use import CASES, measure_original, require

CAMERA_SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def speed(actor):
    vector = actor.get_velocity()
    return math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)


def steer_to(actor, point):
    pose = actor.get_transform()
    target_yaw = math.degrees(math.atan2(point[1] - pose.location.y,
                                          point[0] - pose.location.x))
    error = ((target_yaw - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35))


class Cameras:
    def __init__(self, world, carla, ego, center, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        poses = ((-20, -15, 28, -55), (-14, -4, 10, -25),
                 (3, -8, 9, -40), (0, 0, 1.55, 0))
        try:
            for (name, width, height), (dx, dy, z, pitch) in zip(CAMERA_SPECS, poses):
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                mounted = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if mounted else
                            carla.Location(x=center[0] + dx, y=center[1] + dy, z=z))
                sensor = world.spawn_actor(blueprint,
                                           carla.Transform(location, carla.Rotation(pitch=pitch)),
                                           attach_to=ego if mounted else None)
                require(sensor is not None, "original camera spawn failed: " + name)
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
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                errors.append(repr(error))
        for name, encoder in self.encoders.items():
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    errors.append("camera encoder failed: " + name)
            except BaseException as error:
                errors.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        self.sensors = []
        self.encoders = {}
        if errors:
            raise RuntimeError("; ".join(errors))


def transform(carla, point, yaw):
    return carla.Transform(carla.Location(x=point[0], y=point[1], z=0.4),
                           carla.Rotation(yaw=yaw))


def run_native(config, scene, scene_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    require(output.is_dir(), "Native attempt directory must already exist")
    case = next(item for item in CASES if config["selected_case_id"].endswith("__" + item.case_id))
    site = scene["site"]
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    actors = []
    cameras = capture = frame_map = None
    phase, errors, restored = "initializing", [], False
    rows = []
    try:
        archive = output / "reviewed-scene-packet"
        archive.mkdir(exist_ok=False)
        shutil.copy2(scene_path, archive / "scene.json")
        for item in scene["sources"].values():
            source = (Path(scene_path).parent / item["path"]).resolve()
            target = archive / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        require(world.get_map().name == scene["map_id"], "reviewed Native map ID differs")
        digest = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        require(digest == scene["opendrive_sha256"], "reviewed original map bytes differ")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = site["protected_route"]["waypoints_xy"]
        ego_route = site["ego_routes"][case.ego_path]["waypoints_xy"]
        stage_m = config.get("engineering", {}).get("ego_start_shift_m", 0)
        require(stage_m in (0, -3), "unreviewed engineering start shift")
        if stage_m:
            delta = (ego_route[1][0] - ego_route[0][0], ego_route[1][1] - ego_route[0][1])
            norm = math.hypot(*delta)
            require(norm > 1, "ego source route too short")
            ego_route = [[ego_route[0][0] + stage_m * delta[0] / norm,
                          ego_route[0][1] + stage_m * delta[1] / norm], *ego_route[1:]]
        poses = (("protected", scene["protected_blueprint_id"], route[0], route[1],
                  site["lane_ids"]["protected"]),
                 ("ego", scene["ego_blueprint_id"], ego_route[0], ego_route[1],
                  site["lane_ids"]["adjacent"]))
        for role, blueprint_id, start, next_point, lane_id in poses:
            yaw = math.degrees(math.atan2(next_point[1] - start[1], next_point[0] - start[0]))
            pose = transform(carla, start, yaw)
            waypoint = world.get_map().get_waypoint(pose.location, project_to_road=False)
            require(waypoint is not None and str(waypoint.lane_id) == str(lane_id),
                    "reviewed Native spawn lane differs: " + role)
            actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id), pose)
            require(actor is not None and actor.type_id == blueprint_id,
                    "reviewed Native participant spawn failed: " + role)
            actors.append(actor)
        protected, ego = actors
        write(output / "acquisition-provenance.json", {"provenance_kind": "native",
              "diagnostic_fixture": False, "method": "original CARLA protected-lane run"})
        cameras = Cameras(world, carla, ego, route[len(route) // 2], output)
        capture = PipelineCapture(client, ego, output, config["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        phase = "capturing"
        scene_sha = sha(scene_path)
        with (output / "protected-lane-history.jsonl").open("x", buffering=1) as stream:
            for index in range(round(config["duration_s"] * config["rate_hz"])):
                for actor, path, target_speed in ((protected, route, 6 if case.protected_driven else 0),
                                                  (ego, ego_route, 7)):
                    if target_speed == 0:
                        actor.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
                    else:
                        target = path[min(index // 100 + 1, len(path) - 1)]
                        current_speed = speed(actor)
                        actor.apply_control(carla.VehicleControl(
                            throttle=.25 if current_speed < target_speed else 0,
                            brake=.2 if current_speed > target_speed + .5 else 0,
                            steer=steer_to(actor, target)))
                frame = world.tick()
                snapshot_frame = world.get_snapshot()
                require(snapshot_frame.frame == frame, "original Native frame identity changed")
                time_s = snapshot_frame.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                ego_pose = ego.get_transform().location
                protected_pose = protected.get_transform().location
                for role, actor, location in (("ego", ego, ego_pose),
                                              ("protected", protected, protected_pose)):
                    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
                    require(waypoint is not None, "participant left reviewed drivable map: " + role)
                row = {"original_frame": frame, "time_s": time_s,
                       "source_sha256": scene_sha,
                       "ego_pose_sha256": hashlib.sha256(repr(ego.get_transform()).encode()).hexdigest(),
                       "protected_pose_sha256": hashlib.sha256(repr(protected.get_transform()).encode()).hexdigest(),
                       "map_source_sha256": site["map_source_sha256"],
                       "lane_source_sha256": site["lane_source_sha256"],
                       "highway_source_sha256": site["highway_source_sha256"],
                       "ego_id": ego.id, "protected_id": protected.id,
                       "ego_kind": "motor_vehicle", "protected_kind": case.protected_kind,
                       "ego_xy": [ego_pose.x, ego_pose.y],
                       "protected_xy": [protected_pose.x, protected_pose.y],
                       "protected_speed_mps": speed(protected)}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / "protected-lane-scene.json", scene)
        write(output / "protected-lane-measurement.json", measure_original(rows, site, case))
        names = ["trace.jsonl", "video_frames.jsonl", "protected-lane-history.jsonl",
                 "protected-lane-scene.json", "protected-lane-measurement.json", "road.xodr",
                 "carla_recorder.log", *[name + ".mkv" for name, _, _ in CAMERA_SPECS]]
        names.extend(str(p.relative_to(output)) for p in archive.rglob("*") if p.is_file())
        write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(output / name)}
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
        for actor in reversed(actors):
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
                         restoration={"restored": True, "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in CAMERA_SPECS},
                         context={"protected_lane_case": config["selected_case_id"]})
        else:
            write(output / "native-run-status.json", {"phase": phase, "errors": errors,
                                                       "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
