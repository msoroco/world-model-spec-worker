"""Prospective original Native capture for the two C228817 door cases.

Door commands and actor positions are recorded as separate facts. The capture
does not turn a command into a measured door pose or an occupancy change.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import shutil
import subprocess
from pathlib import Path

from controller import FRAMES
from door_actuation import VIEWS, apply_door_command, validate_setup


BASE = "training__C228817__NRS-484B-153-3__motor_vehicle_driver__probe_"
SCHEDULE = {BASE + "1": "closes_after_transfer",
            BASE + "2": "remains_open"}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    case_id = config.get("case_id")
    _require(case_id in SCHEDULE, "Unknown exact door case")
    _require((config.get("law_id"), config.get("cell_id"), config.get("actor")) ==
             ("NRS-484B-153-3", "C228817", "motor_vehicle_driver"),
             "Wrong law, cell or actor")
    _require(config.get("frozen_cell") ==
             {"layout": "road", "maneuver": "load_unload", "control": "other_vehicle"},
             "Wrong frozen cell")
    _require(config.get("rate_hz") == 20 and config.get("duration_frames") == FRAMES
             and config.get("duration_s") == 30,
             "Full 600-frame 20 Hz capture required")
    _require(config.get("schedule") == SCHEDULE[case_id],
             "Exact door schedule differs")
    cameras = config.get("cameras")
    _require(isinstance(cameras, list) and
             tuple(c.get("name") for c in cameras) == VIEWS,
             "Four original source cameras required")
    for camera in cameras:
        _require(all(type(camera.get(k)) is int and camera[k] >= 16
                     for k in ("width", "height"))
                 and camera.get("fps") == 20
                 and type(camera.get("fov_deg")) in (int, float)
                 and len(camera.get("location_xyz_m", [])) == 3
                 and len(camera.get("rotation_pyr_deg", [])) == 3,
                 "Camera optics, pose or cadence missing")
    _require(config.get("vehicle_blueprint") == "vehicle.tesla.model3"
             and config.get("passing_vehicle_blueprint") == "vehicle.tesla.model3"
             and config.get("walker_blueprint", "").startswith("walker.pedestrian."),
             "Original actor blueprints required")
    _require(config.get("physical_verified") is False
             and config.get("legal_verdict") is None
             and config.get("door_state_observed_by_command") is False,
             "Command cannot establish physical door motion or legal result")
    return {"case_id": case_id, "schedule": SCHEDULE[case_id],
            "frames": FRAMES, "source_cameras": list(VIEWS),
            "carla_contacted": False, "physical_verified": False}


def _camera_pose(carla, camera):
    x, y, z = camera["location_xyz_m"]
    pitch, yaw, roll = camera["rotation_pyr_deg"]
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


def _xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _speed(actor):
    vector = actor.get_velocity()
    return math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)


def _lateral_offset(ego, other):
    reference = ego.get_transform()
    position = other.get_transform().location
    direction = reference.get_right_vector()
    delta = position - reference.location
    # CARLA right-vector positive is ego right; meter uses positive for left.
    return -(delta.x * direction.x + delta.y * direction.y + delta.z * direction.z)


def _pixel_packet(image, camera, np):
    bgra = np.frombuffer(image.raw_data, dtype=np.uint8)
    bgra = bgra.reshape(camera["height"], camera["width"], 4)
    return bgra[:, :, :3][:, :, ::-1].tobytes()


def execute(config, output_dir, review_path, host, port):
    checked = check(config)
    _require(review_path, "Original Native scene review path required")
    review = json.loads(Path(review_path).read_text())
    source = validate_setup(review, config["schedule"])
    _require(review.get("case_id") == config["case_id"],
             "Original scene review binds another exact case")
    # Read source-bound index/geometry choices before any simulator contact.
    setup = review.get("native_setup", {})
    _require(all(type(setup.get(name)) is int and setup[name] >= 0
                 for name in ("ego_spawn_index", "passing_spawn_index", "walker_spawn_index")),
             "Original actor spawn indices required")
    _require(setup.get("door") in ("FL", "FR", "RL", "RR"),
             "Original vehicle door identifier required")
    _require((source["door_side"] == "left") == setup["door"].endswith("L"),
             "Original door identifier differs from traffic side")
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    destination = Path(output_dir)
    _require(destination.is_dir() and (destination / "config.json").is_file(),
             "Runtime-materialized Native bundle required")
    for name, ref in review["sources"].items():
        shutil.copyfile(ref["path"], destination / ("original-" + name + ".json"))
    (destination / "original-scene-review.json").write_text(
        json.dumps(review, indent=2, allow_nan=False) + "\n")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original_world = snapshot(client)
    actors, sensors, encoders, logs = [], [], {}, {}
    packets = queue.Queue()
    try:
        _require(world.get_map().name == source["map_name"],
                 "Original map source differs from CARLA world")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        _require(max(setup[name] for name in
                     ("ego_spawn_index", "passing_spawn_index", "walker_spawn_index")) < len(spawns),
                 "Original actor spawn index unavailable")
        blueprints = world.get_blueprint_library()
        ego = world.try_spawn_actor(blueprints.find(config["vehicle_blueprint"]),
                                    spawns[setup["ego_spawn_index"]])
        _require(ego is not None, "Ego spawn occupied")
        actors.append(ego)
        passing = world.try_spawn_actor(
            blueprints.find(config["passing_vehicle_blueprint"]),
            spawns[setup["passing_spawn_index"]])
        _require(passing is not None, "Passing-vehicle spawn occupied")
        actors.append(passing)
        walker = world.try_spawn_actor(blueprints.find(config["walker_blueprint"]),
                                       spawns[setup["walker_spawn_index"]])
        _require(walker is not None, "Passenger walker spawn occupied")
        actors.append(walker)
        # Native observed identifiers supersede authored source labels.
        _require(ego.id != passing.id and ego.id != walker.id and passing.id != walker.id,
                 "Original participant identities overlap")
        door = getattr(carla.VehicleDoor, setup["door"])
        for camera in config["cameras"]:
            blueprint = blueprints.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            sensor = world.spawn_actor(blueprint, _camera_pose(carla, camera), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            name = camera["name"]
            logs[name] = (destination / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{camera['width']}x{camera['height']}", "-r", "20",
                "-i", "pipe:0", "-an", "-c:v", "ffv1",
                str(destination / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(lambda image, view=name: packets.put((view, image)))
        with PipelineCapture(client, ego, destination, config["case_id"],
                             required_observations=config.get("required_atoms", [])) as capture, \
                FrameMap(destination / "video_frames.jsonl") as frame_map, \
                (destination / "native-door-trace.jsonl").open("x", buffering=1) as trace:
            for index in range(FRAMES):
                commanded = apply_door_command(ego, door, config["schedule"], index)
                ego.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
                passing.apply_control(carla.VehicleControl(
                    throttle=0.3 if 110 <= index <= 210 else 0.0,
                    brake=0.0 if 110 <= index <= 210 else 1.0))
                walker.apply_control(carla.WalkerControl(
                    direction=walker.get_transform().get_right_vector(),
                    speed=0.8 if 190 <= index <= 225 else 0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = packets.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    camera = next(c for c in config["cameras"] if c["name"] == name)
                    encoders[name].stdin.write(_pixel_packet(image, camera, np))
                    seen.add(name)
                timestamp = world.get_snapshot().timestamp.elapsed_seconds
                frame_map.append(native_frame, index / 20,
                                 native_elapsed_s=timestamp)
                capture.capture(native_frame, index / 20,
                                extra={"video_frame": index, "door_command": commanded["door_command"]})
                trace.write(json.dumps({
                    "source_kind": "original_native_observation",
                    "video_frame": index, "native_frame": native_frame,
                    "native_elapsed_s": timestamp, "time_s": index / 20,
                    "driver_actor_id": ego.id, "passing_actor_id": passing.id,
                    "pedestrian_actor_id": walker.id,
                    "ego_position_m": _xyz(ego.get_transform().location),
                    "ego_speed_mps": _speed(ego),
                    "passing_position_m": _xyz(passing.get_transform().location),
                    "passing_lateral_offset_m": _lateral_offset(ego, passing),
                    "pedestrian_position_m": _xyz(walker.get_transform().location),
                    "door_state_observed": None,
                    "occupancy_delta_observed": None,
                    "transfer_complete_observed": None,
                    "requested": commanded}) + "\n")
    finally:
        failures = []
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as exc:
                failures.append("sensor stop: " + str(exc))
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=120) != 0:
                    failures.append("encoder failed: " + name)
            except BaseException as exc:
                failures.append("encoder close: " + str(exc))
            finally:
                logs[name].close()
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as exc:
                failures.append("actor destroy: " + str(exc))
        try:
            restore(client, original_world)
        except BaseException as exc:
            failures.append("world restore: " + str(exc))
        if failures:
            raise RuntimeError("; ".join(failures))
    return {"case_id": config["case_id"], "native_frames_requested": FRAMES,
            "door_state_observed": False, "physical_verified": False,
            "legal_verdict": None, "checked": checked}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--scene-review")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        _require(args.output_dir is not None, "--output-dir required")
        print(json.dumps(execute(config, args.output_dir,
                                 args.scene_review or os.environ.get("SCENARIO_DOOR_SCENE_REVIEW"),
                                 args.host, args.port), sort_keys=True))
