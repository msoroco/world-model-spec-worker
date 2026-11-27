"""Original Native angle-parking acquisition, with reviewed-site admission.

CARLA is imported only in run_native. Captured geometry is an observation; the
requested angle and halt purpose are construction targets, never legal findings.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def control(position, yaw_deg, velocity, target, target_yaw_deg, reached, held_frames,
            activity, total_frames, brake_gain=0.7):
    if activity not in {"stop", "stand", "park"}:
        raise ValueError("unsupported exact halt activity")
    target_yaw = math.radians(target_yaw_deg)
    distance = math.dist(position, target)
    direction = math.atan2(target[1] - position[1], target[0] - position[0]) if distance > 0.05 else target_yaw
    yaw = math.radians(yaw_deg)
    heading_goal = target_yaw if distance < 3.0 else direction
    error = math.atan2(math.sin(heading_goal - yaw), math.cos(heading_goal - yaw))
    steer = max(-0.65, min(0.65, error * 1.2))
    target_reached = reached or (distance < 1.1 and abs(math.degrees(error)) < 8 and velocity < 0.25)
    planned_hold = {"stop": 60, "stand": 160, "park": total_frames}[activity]
    if target_reached and held_frames < planned_hold:
        return {"steer": 0.0, "throttle": 0.0, "brake": 1.0,
                "hand_brake": activity == "park"}, "hold", True
    if target_reached and activity != "park":
        return {"steer": 0.0, "throttle": 0.2, "brake": 0.0,
                "hand_brake": False}, "depart", True
    braking_distance = velocity * velocity / 4.0 + 1.5
    if distance <= braking_distance:
        return {"steer": steer, "throttle": 0.0, "brake": brake_gain,
                "hand_brake": False}, "approach", target_reached
    return {"steer": steer, "throttle": 0.25 if velocity < 3 else 0.0,
            "brake": 0.0, "hand_brake": False}, "approach", target_reached


class FourCameras:
    def __init__(self, world, carla, ego, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 2, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(CAMERAS, poses):
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                sensor = world.spawn_actor(blueprint, carla.Transform(
                    location, carla.Rotation(pitch=pitch)), attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                       f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                       "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                       str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame differs from original world frame: " + name)
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


def run_native(cfg, site, records, site_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("Native attempt directory must already exist")
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    actors = []
    cameras = capture = frame_map = None
    phase = "initializing"
    errors = []
    restored = False
    frame_count = 0
    held = 0
    try:
        mapping = world.get_map()
        if mapping.name != site["map_id"] or sha_opendrive(mapping) != records["map"]["opendrive_sha256"]:
            raise ValueError("loaded original OpenDRIVE differs from reviewed source")
        start = site["approach_xy"]
        target = site["target_xy"]
        start_wp = mapping.get_waypoint(carla.Location(x=start[0], y=start[1], z=0))
        target_wp = mapping.get_waypoint(carla.Location(x=target[0], y=target[1], z=0))
        if not start_wp or not target_wp or start_wp.road_id != site["road_id"] or target_wp.road_id != site["road_id"]:
            raise ValueError("Native approach or target differs from reviewed highway")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        device = records["official_device"]
        pose = device["prop_pose"]
        prop = world.spawn_actor(library.find(device["prop_blueprint_id"]), carla.Transform(
            carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
            carla.Rotation(yaw=pose["yaw_deg"])))
        actors.append(prop)
        if prop.type_id != device["prop_blueprint_id"]:
            raise ValueError("Native device prop readback differs")
        ego = world.spawn_actor(library.find(site["vehicle_blueprint_id"]), carla.Transform(
            carla.Location(x=start[0], y=start[1], z=start_wp.transform.location.z + 0.5),
            carla.Rotation(yaw=site["approach_heading_degrees"])))
        actors.append(ego)
        if ego.type_id != site["vehicle_blueprint_id"]:
            raise ValueError("Native vehicle blueprint readback differs")
        source_output = output / "reviewed-site"
        source_output.mkdir(exist_ok=False)
        shutil.copy2(site_path, source_output / "site.json")
        for ref in site["sources"].values():
            src = (Path(site_path).parent / ref["path"]).resolve()
            dest = source_output / ref["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        context = {"assignment_id": cfg["assignment_id"], "case_id": cfg["selected_case_id"],
                   "site_sha256": sha(site_path), "map_sha256": records["map"]["opendrive_sha256"],
                   "device_source_sha256": site["sources"]["official_device"]["sha256"],
                   "roadway_source_sha256": site["sources"]["roadway"]["sha256"],
                   "purpose_source_sha256": site["sources"]["purpose"]["sha256"],
                   "official_device_actor_id": prop.id, "vehicle_actor_id": ego.id,
                   "curb_edge_xy": records["roadway"]["curb_edge_xy"],
                   "indicated_angle_degrees": device["indicated_angle_degrees"],
                   "requested_activity": site["requested_activity"],
                   "requested_orientation": site["requested_orientation"]}
        write(output / "angle-context.json", context)
        write(output / "acquisition-provenance.json", {"provenance_kind": "native",
             "diagnostic_fixture": False, "method": "original CARLA live angle-parking run"})
        cameras = FourCameras(world, carla, ego, target, output)
        capture = PipelineCapture(client, ego, output, cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        reached = False
        phase = "capturing"
        total_frames = round(cfg["duration_s"] * cfg["rate_hz"])
        with (output / "angle-history.jsonl").open("x", buffering=1) as stream:
            for index in range(total_frames):
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                position = [transform.location.x, transform.location.y]
                command, state, reached = control(position, transform.rotation.yaw, speed,
                    target, site["target_heading_degrees"], reached, held,
                    site["requested_activity"], total_frames, cfg.get("engineering_brake_gain", 0.7))
                ego.apply_control(carla.VehicleControl(**command))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("Native world frame differs from snapshot")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                if state == "hold" and speed <= 0.1:
                    held += 1
                row = {"frame": frame, "sample_index": index, "time_s": time_s,
                       "body_yaw_degrees": transform.rotation.yaw,
                       "vehicle_vertices": [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(transform)],
                       "speed_mps": speed, "position_xy": [transform.location.x, transform.location.y],
                       "halt_observed": state == "hold" and speed <= 0.1,
                       "vehicle_actor_id": ego.id, "device_actor_id": prop.id,
                       "control_command": command, "control_state": state,
                       "requested_activity": site["requested_activity"]}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                frame_count += 1
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ["trace.jsonl", "video_frames.jsonl", "angle-history.jsonl",
                 "angle-context.json", "road.xodr", "carla_recorder.log", "reviewed-site/site.json",
                 *["reviewed-site/" + ref["path"] for ref in site["sources"].values()],
                 *[name + ".mkv" for name, _, _ in CAMERAS]]
        write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(output / name)} for name in names})
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
            seal_capture(output, frames=frame_count,
                         restoration={"restored": True,
                                      "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in CAMERAS},
                         context={"angle_parking": context, "halt_frames": held})
        else:
            write(output / "native-run-status.json", {"phase": phase, "errors": errors,
                                                       "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")


def sha_opendrive(mapping):
    return hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()
