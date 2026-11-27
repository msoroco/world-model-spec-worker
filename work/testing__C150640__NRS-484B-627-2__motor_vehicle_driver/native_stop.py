"""Original CARLA acquisition for a reviewed one-way stop and following traffic.

No module import connects to CARLA. The local operator supplies reviewed source
bytes, a matching map and an original attempt directory before this runs.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from stop_model import BY_NAME, controller_target, longitudinal_gap, measure_original, sha


CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def xy(actor):
    location = actor.get_location()
    return (float(location.x), float(location.y))


def footprint(actor):
    pose = actor.get_transform()
    extent = actor.bounding_box.extent
    centre = actor.bounding_box.location
    angle = math.radians(pose.rotation.yaw)
    x0 = pose.location.x + centre.x * math.cos(angle) - centre.y * math.sin(angle)
    y0 = pose.location.y + centre.x * math.sin(angle) + centre.y * math.cos(angle)
    return [[x0 + a * math.cos(angle) - b * math.sin(angle),
             y0 + a * math.sin(angle) + b * math.cos(angle)]
            for a, b in ((-extent.x, -extent.y), (extent.x, -extent.y),
                         (extent.x, extent.y), (-extent.x, extent.y))]


def station(point, route):
    start, end = route[0], route[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1:
        raise ValueError("reviewed route too short")
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length


def steer(actor, target):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(target[1] - pose.location.y,
                                      target[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35))


class FourCameras:
    def __init__(self, world, carla, ego, follower, stop_xy, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        try:
            poses = ((-18, -14, 28, -55), (-24, -4, 10, -20),
                     (3, -11, 10, -35), (0, 0, 1.6, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(CAMERAS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                loc = (carla.Location(x=dx, y=dy, z=z) if attached else
                       carla.Location(x=stop_xy[0] + dx, y=stop_xy[1] + dy, z=z))
                pose = carla.Transform(loc, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, pose, attach_to=follower if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                sensor.listen(lambda image, target=frames: target.put_nowait(image))
                self.encoders[name] = subprocess.Popen(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                     "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                     f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                     "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))],
                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        for name, _, _ in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame disagrees with original Native frame: " + name)
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


def spawn(world, carla, scene, role, owned):
    point = scene[role + "_spawn_xy"]
    waypoint = world.get_map().get_waypoint(
        carla.Location(x=point[0], y=point[1], z=0), project_to_road=False)
    if waypoint is None:
        raise ValueError("reviewed original spawn waypoint missing: " + role)
    blueprint_id = scene[role + "_blueprint_id"]
    bp = world.get_blueprint_library().find(blueprint_id)
    actor = world.try_spawn_actor(bp, carla.Transform(
        carla.Location(x=point[0], y=point[1], z=waypoint.transform.location.z + .5),
        waypoint.transform.rotation))
    if actor is None or actor.type_id != blueprint_id:
        raise ValueError("reviewed original actor spawn failed: " + role)
    owned.append(actor)
    return actor


def run_native(config, scene, scene_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("original attempt directory must already exist")
    case = BY_NAME[config["selected_case_id"].split("__")[-1]]
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    owned, cameras, capture, frame_map = [], None, None, None
    rows, errors, phase, restored = [], [], "initializing", False
    try:
        archive = output / "reviewed-stop-packet"
        archive.mkdir(exist_ok=False)
        shutil.copy2(scene_path, archive / "scene.json")
        for item in scene["sources"].values():
            source = (Path(scene_path).parent / item["path"]).resolve()
            destination = archive / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        map_source = Path(scene_path).parent / scene["sources"]["map"]["path"]
        map_reference = json.loads(map_source.read_text(encoding="utf-8"))
        actual_opendrive = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        if world.get_map().name != scene["map_id"] or actual_opendrive != map_reference.get("opendrive_sha256"):
            raise ValueError("reviewed original one-way map differs from Native world")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        ego = spawn(world, carla, scene, "ego", owned)
        follower = spawn(world, carla, scene, "follower", owned)
        if ego.id == follower.id:
            raise ValueError("original actor identities collapse")
        conflict = world.get_actor(scene["conflict_actor_id"]) if case.stop_reason == "safety_conflict" else None
        direction = world.get_actor(scene["official_direction_actor_id"]) if case.stop_reason == "official_direction" else None
        if case.stop_reason == "safety_conflict" and conflict is None:
            raise ValueError("reviewed original safety conflict actor absent")
        if case.stop_reason == "official_direction" and direction is None:
            raise ValueError("reviewed original official direction actor absent")
        write(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA one-way stop and follower readback"})
        cameras = FourCameras(world, carla, ego, follower, scene["ego_stop_xy"], output)
        capture = PipelineCapture(client, ego, output, config["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        route = scene["one_way_route"]
        heading = math.atan2(route[-1][1] - route[0][1], route[-1][0] - route[0][0])
        phase = "capturing"
        with (output / "stop-history.jsonl").open("x", buffering=1) as stream:
            for index in range(config["duration_s"] * config["rate_hz"]):
                ego_point, follower_point = xy(ego), xy(follower)
                body_gap = longitudinal_gap(ego_point, follower_point, heading,
                                            ego.bounding_box.extent.x * 2,
                                            follower.bounding_box.extent.x * 2)
                trigger = config["engineering"]["stop_trigger_frame"]
                controls = controller_target(case, index, speed(ego), speed(follower),
                                             body_gap, trigger)
                ego_target = scene["ego_stop_xy"] if index >= trigger else route[-1]
                follower_target = (scene["follower_pass_route"][-1] if case.follower_action == "pass"
                                   else route[-1])
                ego.apply_control(carla.VehicleControl(**controls["ego"], steer=steer(ego, ego_target)))
                follower.apply_control(carla.VehicleControl(
                    **controls["follower"], steer=steer(follower, follower_target)))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("original world frame changed")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                ego_point, follower_point = xy(ego), xy(follower)
                body_gap = longitudinal_gap(ego_point, follower_point, heading,
                                            ego.bounding_box.extent.x * 2,
                                            follower.bounding_box.extent.x * 2)
                row = {"original_frame": frame, "time_s": time_s,
                       "ego_id": ego.id, "follower_id": follower.id,
                       "ego_speed_mps": speed(ego), "follower_speed_mps": speed(follower),
                       "ego_footprint_xy": footprint(ego),
                       "follower_route_station_m": station(follower_point, route),
                       "ego_route_station_m": station(ego_point, route),
                       "body_gap_m": body_gap,
                       "follower_ahead_of_ego": station(follower_point, route) > station(ego_point, route),
                       "conflict_readback": {"actor_id": conflict.id,
                                             "position_xy": xy(conflict)} if conflict else None,
                       "official_direction_readback": {"actor_id": direction.id,
                                                        "state": str(direction.get_state())} if direction else None,
                       "ego_control": controls["ego"], "follower_control": controls["follower"],
                       "reviewed_scene_sha256": sha(Path(scene_path))}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        write(output / "stop-scene.json", scene)
        write(output / "stop-measurement.json", measure_original(rows, scene, case))
        names = ["trace.jsonl", "video_frames.jsonl", "stop-history.jsonl",
                 "stop-scene.json", "stop-measurement.json", "road.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, _, _ in CAMERAS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob("*") if path.is_file())
        write(output / "acquisition.json", {
            name: {"kind": "original_native", "sha256": sha(output / name)} for name in names})
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
        for actor in reversed(owned):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            restored = restore(client, saved)["restored"]
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={"restored": True, "settings_readback": "original world restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in CAMERAS},
                         context={"roadway_stop_case": config["selected_case_id"]})
        else:
            write(output / "native-run-status.json", {"phase": phase, "errors": errors,
                                                      "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
