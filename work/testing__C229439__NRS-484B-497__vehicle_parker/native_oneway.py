"""Source-checked original 20 Hz one-way parking acquisition.

The runner records observations; it never decides whether a device has legal
authority or whether a recorded halt is standing or parking under the statute.
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


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def body_vertices(actor):
    return [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def control(distance, velocity, phase, activity, brake_gain=0.68):
    if phase == "hold":
        return {"throttle": 0, "brake": 1, "hand_brake": activity == "park"}
    if phase == "depart":
        return {"throttle": 0.22 if velocity < 4 else 0,
                "brake": 0, "hand_brake": False}
    if distance <= velocity * velocity / 5 + 1:
        return {"throttle": 0, "brake": brake_gain, "hand_brake": False}
    return {"throttle": 0.25 if velocity < 5 else 0,
            "brake": 0, "hand_brake": False}


def phase_for(activity, reached, held_frames, total_frames):
    if activity not in ("stop", "stand", "park"):
        raise ValueError("unsupported requested activity")
    if not reached:
        return "approach"
    planned = {"stop": 60, "stand": 160, "park": total_frames}[activity]
    return "depart" if activity != "park" and held_frames >= planned else "hold"


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
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                sensor = world.spawn_actor(bp, carla.Transform(location, carla.Rotation(pitch=pitch)),
                                           attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                        f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                        "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                        str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(args, stdin=subprocess.PIPE,
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


def validate_loaded_road(mapping, carla, records, site):
    road = records["roadway"]
    expected = {lane["lane_id"] for lane in road["marked_lanes"]}
    observed = set()
    for lane in road["marked_lanes"]:
        sample = lane.get("sample_xy")
        if not isinstance(sample, list) or len(sample) != 2:
            raise ValueError("reviewed marked lane sample required")
        wp = mapping.get_waypoint(carla.Location(x=sample[0], y=sample[1], z=0))
        if wp is None or wp.road_id != site["road_id"] or wp.lane_id != lane["lane_id"]:
            raise ValueError("Native marked lane identity differs from reviewed road")
        observed.add(wp.lane_id)
    if observed != expected:
        raise ValueError("Native marked lane inventory incomplete")
    return sorted(observed)


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
    try:
        mapping = world.get_map()
        if (mapping.name != site["map_id"] or
                hashlib.sha256(mapping.to_opendrive().encode()).hexdigest() !=
                records["map"].get("opendrive_sha256")):
            raise ValueError("loaded Native OpenDRIVE differs from reviewed source")
        lane_ids = validate_loaded_road(mapping, carla, records, site)
        road = records["roadway"]
        target = site["target_xy"]
        start = site["approach_xy"]
        start_wp = mapping.get_waypoint(carla.Location(x=start[0], y=start[1], z=0))
        target_wp = mapping.get_waypoint(carla.Location(x=target[0], y=target[1], z=0))
        if (not start_wp or not target_wp or start_wp.road_id != site["road_id"]
                or target_wp.road_id != site["road_id"]):
            raise ValueError("Native approach or target is not on reviewed road")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        vehicle_id = site.get("vehicle_blueprint_id", "vehicle.tesla.model3")
        vehicle_bp = library.find(vehicle_id)
        if vehicle_bp is None:
            raise ValueError("reviewed vehicle blueprint unavailable")
        device = records["device_inventory"]
        device_actor_id = None
        if device["devices"]:
            spec = device["devices"][0]
            bp = library.find(spec["prop_blueprint_id"])
            pose = spec["prop_pose"]
            prop = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                carla.Rotation(yaw=pose["yaw_deg"])))
            actors.append(prop)
            if prop.type_id != spec["prop_blueprint_id"]:
                raise ValueError("erected Native device prop readback differs")
            device_actor_id = prop.id
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=start[0], y=start[1], z=start_wp.transform.location.z + 0.5),
            carla.Rotation(yaw=site["target_heading_deg"])))
        actors.append(ego)
        if ego.type_id != vehicle_id:
            raise ValueError("Native vehicle blueprint readback differs")
        context = {"assignment_id": cfg["assignment_id"], "case_id": cfg["selected_case_id"],
                   "map_sha256": records["map"]["opendrive_sha256"],
                   "road_origin_xy": road["origin_xy"], "road_forward_xy": road["forward_xy"],
                   "roadway_polygon_xy": road["roadway_polygon_xy"],
                   "marked_lane_count": len(lane_ids), "native_lane_ids": lane_ids,
                   "one_way_restriction": records["restriction"]["one_way"],
                   "device_kind": device["kind"],
                   "device_actor_id": device_actor_id, "vehicle_actor_id": ego.id,
                   "roadway_public_use_source": site["sources"]["roadway"]["sha256"],
                   "roadway_boundary_source": site["sources"]["roadway"]["sha256"],
                   "marked_lanes_source": site["sources"]["roadway"]["sha256"],
                   "direction_restriction_source": site["sources"]["restriction"]["sha256"],
                   "device_inventory_source": site["sources"]["device_inventory"]["sha256"],
                   "device_erection_source": site["sources"]["device_inventory"]["sha256"],
                   "device_official_status_source": site["sources"]["authority"]["sha256"],
                   "device_instruction_source": site["sources"]["device_inventory"]["sha256"],
                   "device_governed_space_source": site["sources"]["device_inventory"]["sha256"],
                   "parking_person_source": site["sources"]["person"]["sha256"],
                   "halt_purpose_source": site["sources"]["purpose"]["sha256"],
                   "site_sha256": sha(site_path)}
        site_output = output / "reviewed-site"
        site_output.mkdir(exist_ok=False)
        shutil.copy2(site_path, site_output / "site.json")
        for ref in site["sources"].values():
            source = (Path(site_path).parent / ref["path"]).resolve()
            target_path = site_output / ref["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_path)
        write(output / "parking-context.json", context)
        write(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA live one-way parking run"})
        cameras = FourCameras(world, carla, ego, target, output)
        capture = PipelineCapture(client, ego, output, cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        reached = False
        held = 0
        activity = site["requested_activity"]
        brake_gain = cfg.get("engineering_brake_gain", 0.68)
        phase = "capturing"
        with (output / "parking-history.jsonl").open("x", buffering=1) as stream:
            for index in range(round(cfg["duration_s"] * cfg["rate_hz"])):
                transform = ego.get_transform()
                distance = math.dist([transform.location.x, transform.location.y], target)
                if distance <= 1.5:
                    reached = True
                state = phase_for(activity, reached, held, round(cfg["duration_s"] * cfg["rate_hz"]))
                command = control(distance, speed(ego), state, activity, brake_gain)
                ego.apply_control(carla.VehicleControl(**command))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("Native world frame differs from snapshot")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                if state == "hold" and speed(ego) <= 0.1:
                    held += 1
                transform = ego.get_transform()
                row = {"frame": frame, "sample_index": index, "time_s": time_s,
                       "vehicle_vertices": body_vertices(ego), "speed_mps": speed(ego),
                       "position_m": [transform.location.x, transform.location.y],
                       "vehicle_actor_id": ego.id, "device_actor_id": device_actor_id,
                       "control_command": command, "control_state": state,
                       "requested_activity": activity}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                frame_count += 1
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ["trace.jsonl", "video_frames.jsonl", "parking-history.jsonl",
                 "parking-context.json", "road.xodr", "carla_recorder.log",
                 "reviewed-site/site.json",
                 *["reviewed-site/" + ref["path"] for ref in site["sources"].values()],
                 *[name + ".mkv" for name, _, _ in CAMERAS]]
        write(output / "acquisition.json", {name: {"kind": "original_native",
            "sha256": sha(output / name)} for name in names})
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
                         context={"oneway_parking": context, "hold_frames": held})
        else:
            write(output / "native-run-status.json", {"phase": phase, "errors": errors,
                                                       "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
