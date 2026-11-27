"""Operator-owned CARLA acquisition for the two exact bicycle rider probes.

This code is prepared on CPU and requires a later exclusive local CARLA run.
It records original actor and camera sources; no legal or physical outcome is
asserted by a successful process exit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from geometry import EGO_BLUEPRINT, RIDER_BLUEPRINT
from scene import build, camera_plan, command_from_native, fixed_context
from cyclist_response import response_command

ASSIGNMENT = "training__C136495__NRS-484B-270-5a__motor_vehicle_driver"


def check(case_id: str, condition: str, duration_s: int = 30, rate_hz: int = 20,
          candidate: str = "primary") -> dict:
    expected = ASSIGNMENT + "__selected_a21cf01e__condition_" + ("a" if condition == "early_response" else "b")
    if condition not in ("early_response", "later_response") or case_id != expected:
        raise ValueError("Wrong exact cyclist case or comparison condition")
    if duration_s != 30 or rate_hz != 20:
        raise ValueError("Exact four-camera duration plan differs")
    if candidate not in ("primary", "fallback1"):
        raise ValueError("Unknown rider candidate construction")
    return {"case_id": case_id, "condition": condition, "duration_s": duration_s,
            "rate_hz": rate_hz, "candidate_id": candidate,
            "camera_plan": camera_plan(),
            "driver_blueprint": EGO_BLUEPRINT, "rider_blueprint": RIDER_BLUEPRINT,
            "physical_native_verified": False}


def _write_new(path: Path, value) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_row(stream, value) -> None:
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _camera_transform(carla, spec):
    x, y, z = spec["xyz_m"]
    if spec["attachment"] == "ego":
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(pitch=-8, yaw=0))
    target_x, target_y = 90.0, -1.8
    yaw = math.degrees(math.atan2(target_y - y, target_x - x))
    pitch = math.degrees(math.atan2(-z, math.hypot(target_x - x, target_y - y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw))


def _source_row(actor, native_frame: int, time_s: float) -> dict:
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    return {"native_frame": native_frame, "time_s": time_s,
            "x_m": pose.location.x, "y_m": pose.location.y,
            "vx_mps": velocity.x, "vy_mps": velocity.y,
            "speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
            "yaw_rad": math.radians(pose.rotation.yaw),
            "actor_id": actor.id, "blueprint_id": actor.type_id,
            "body_width_m": 2 * actor.bounding_box.extent.y,
            "body_length_m": 2 * actor.bounding_box.extent.x}


def execute(output_dir: Path, case_id: str, condition: str, host: str,
            port: int, candidate: str = "primary") -> dict:
    import carla  # Lazy: no CARLA import or server use in CPU checks.
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture

    specification = check(case_id, condition, candidate=candidate)
    output_dir = Path(output_dir).resolve()
    if not output_dir.is_dir() or any((output_dir / name).exists() for name in (
        "actor-frames.jsonl", "camera-frame-map.jsonl", "response-control.jsonl", "video_frames.jsonl",
        "rider-binding.json", "overview.mkv", "approach.mkv",
        "reference_corner.mkv", "driver_reference.mkv",
    )):
        raise ValueError("Use a fresh, operator-owned attempt directory")
    client = carla.Client(host, port)
    client.set_timeout(180)
    prior = client.get_world()
    if prior.get_settings().synchronous_mode or any(
        actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
        for actor in prior.get_actors()
    ):
        raise RuntimeError("Requires an exclusive idle asynchronous CARLA world")
    saved = snapshot(client)
    scene = None
    sensors = []
    collision_events = []
    encoders = {}
    logs = {}
    changed = False
    capture = None
    try:
        changed = True
        scene = build(client, carla, condition, candidate)
        world = scene["world"]
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        actors = scene["actors"]
        capture = PipelineCapture(client, actors["ego"], output_dir, case_id,
                                  visibility=False, required_observations=())
        for actor in actors.values():
            actor.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        camera_queues = {}
        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(
            collision_bp, carla.Transform(carla.Location(x=0, y=0, z=0)),
            attach_to=actors["ego"])
        if collision_sensor is None:
            raise RuntimeError("Original collision sensor spawn failed")
        sensors.append(collision_sensor)
        collision_sensor.listen(lambda event: collision_events.append({
            "native_frame": event.frame,
            "other_actor_id": event.other_actor.id,
            "other_actor_type": event.other_actor.type_id}))
        for spec in camera_plan():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]),
                               ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(blueprint, _camera_transform(carla, spec),
                                       attach_to=actors["ego"] if spec["attachment"] == "ego" else None)
            if sensor is None:
                raise RuntimeError("Native camera spawn failed: " + spec["name"])
            sensors.append(sensor)
            q = queue.Queue()
            camera_queues[spec["name"]] = q
            sensor.listen(q.put)
            log = (output_dir / (spec["name"] + ".encoder.log")).open("x")
            logs[spec["name"]] = log
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f'{spec["width"]}x{spec["height"]}', "-r", "20",
                "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "1",
                str(output_dir / (spec["name"] + ".mkv")),
            ], stdin=subprocess.PIPE, stderr=log)
        actor_path = output_dir / "actor-frames.jsonl"
        camera_path = output_dir / "camera-frame-map.jsonl"
        response_path = output_dir / "response-control.jsonl"
        original_time = world.get_snapshot().timestamp.elapsed_seconds
        with actor_path.open("x") as actor_file, camera_path.open("x") as camera_file, \
             response_path.open("x") as response_file, \
             FrameMap(output_dir / "video_frames.jsonl") as frame_map:
            for index in range(600):
                prior_ego = actors["ego"].get_transform().location
                prior_rider = actors["rider"].get_transform().location
                forward_gap_m = prior_rider.x - prior_ego.x - (
                    actors["ego"].bounding_box.extent.x +
                    actors["rider"].bounding_box.extent.x)
                response = None
                response_speed = None
                for role in ("ego", "rider"):
                    actor = actors[role]
                    command = command_from_native(scene["controllers"][role], actor, .05)
                    if role == "ego":
                        observed_speed = actor.get_velocity()
                        response_speed = math.hypot(observed_speed.x, observed_speed.y)
                        response = response_command(condition, forward_gap_m,
                                                    response_speed)
                        # Longitudinal response differs; steering still follows
                        # the identical measured-pose route in both cases.
                        command.update(response)
                    actor.apply_control(carla.VehicleControl(
                        throttle=command["throttle"], brake=command["brake"],
                        steer=command["steer"], hand_brake=command["hand_brake"]))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - original_time
                observed = {role: _source_row(actor, frame, time_s)
                            for role, actor in actors.items()}
                capture.capture(frame, time_s,
                                extra={"c136495_rider_original": observed})
                _write_row(actor_file, {"native_frame": frame, "time_s": time_s,
                                        "actors": observed})
                _write_row(response_file, {"native_frame": frame, "time_s": time_s,
                                           "condition": condition,
                                           "source_forward_gap_m": forward_gap_m,
                                           "source_ego_speed_mps": response_speed,
                                           "command": response})
                camera_frames = {}
                for spec in camera_plan():
                    image = camera_queues[spec["name"]].get(timeout=30)
                    if image.frame != frame or image.width != spec["width"] or image.height != spec["height"]:
                        raise RuntimeError("Original camera frame join differs: " + spec["name"])
                    encoder = encoders[spec["name"]]
                    encoder.stdin.write(image.raw_data)
                    camera_frames[spec["name"]] = image.frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                _write_row(camera_file, {"native_frame": frame, "time_s": time_s,
                                         "camera_frames": camera_frames})
        capture.close(confirmed=True)
        collision_sensor.stop()
        with (output_dir / "collision-events.jsonl").open("x") as stream:
            for event in sorted(collision_events, key=lambda row: row["native_frame"]):
                _write_row(stream, event)
        for name, encoder in encoders.items():
            encoder.stdin.close()
            if encoder.wait(timeout=180) != 0:
                raise RuntimeError("Camera encoder failed: " + name)
        classification = {"driver_actor_role": "motor_vehicle_driver",
                          "driver_blueprint_id": actors["ego"].type_id,
                          "requested_rider_vehicle_type": "bicycle",
                          "rider_blueprint_id": actors["rider"].type_id,
                          "actual_person_riding": "unresolved",
                          "wheel_configuration": "unresolved",
                          "propulsion": "unresolved",
                          "moped_exclusion": "unresolved",
                          "due_care": "unresolved",
                          "native_wheel_radii_m": [
                              wheel.radius / 100.0 for wheel in
                              actors["rider"].get_physics_control().wheels],
                          "observed_body_width_m": {
                              role: 2 * actor.bounding_box.extent.y
                              for role, actor in actors.items()},
                          "observed_body_length_m": {
                              role: 2 * actor.bounding_box.extent.x
                              for role, actor in actors.items()},
                          "classification_review_required": True}
        _write_new(output_dir / "classification.json", classification)
        source_names = ("actor-frames.jsonl", "camera-frame-map.jsonl",
                        "response-control.jsonl",
                        "classification.json", "collision-events.jsonl")
        source_sha = {name: _hash_file(output_dir / name)
                      for name in source_names}
        _write_new(output_dir / "rider-binding.json", {
            "format": "c136495-native-source-manifest-v1", "case_id": case_id,
            "condition": condition, "candidate_id": candidate,
            "camera_plan": specification["camera_plan"],
            "fixed_context": fixed_context(),
            "source_sha256": source_sha, "sha256": source_sha,
            "original_native_capture": True,
            "original_media": {name: _hash_file(output_dir / (name + ".mkv"))
                               for name in ("overview", "approach", "reference_corner", "driver_reference")},
            "physical_native_verified": False})
        return {"case_id": case_id, "frame_count": 600,
                "output_dir": str(output_dir), "physical_native_verified": False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for sensor in sensors:
            sensor.stop()
            sensor.destroy()
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait(timeout=30)
        for log in logs.values():
            log.close()
        if scene is not None:
            for actor in reversed(list(scene["actors"].values())):
                actor.destroy()
        if changed:
            restore(client, saved)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--condition", choices=("early_response", "later_response"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--candidate", choices=("primary", "fallback1"), default="primary")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(check(args.case_id, args.condition,
                               candidate=args.candidate), sort_keys=True))
        return
    configured = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not configured or ".runtime-work" not in Path(configured).parts:
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
    print(json.dumps(execute(Path(args.output), args.case_id, args.condition,
                             args.host, args.port, args.candidate), sort_keys=True))


if __name__ == "__main__":
    main()
