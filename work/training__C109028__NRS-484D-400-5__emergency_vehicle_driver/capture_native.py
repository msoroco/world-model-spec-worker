"""Prospective original CARLA motion/camera acquisition for C109028.

The siren request is recorded only as a request. No CARLA actuator value is
treated as sound. Original microphone and dispatch sources must be joined by
saved processing before any delivery claim.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from geometry import open_drive
from motion import FRAMES, RATE_HZ, request


def _write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def camera_specs():
    return [
        {"name": "overview", "width": 1920, "height": 1080,
         "fov_deg": 100, "xyz_m": [-13, 0, 12], "yaw_deg": 0, "pitch_deg": -13},
        {"name": "approach", "width": 1280, "height": 720,
         "fov_deg": 85, "xyz_m": [3, 0, 3.5], "yaw_deg": 0, "pitch_deg": -2},
        {"name": "reference_corner", "width": 1280, "height": 720,
         "fov_deg": 85, "xyz_m": [-3, 0, 5], "yaw_deg": 0, "pitch_deg": -8},
        {"name": "driver_reference", "width": 1280, "height": 720,
         "fov_deg": 100, "xyz_m": [-7, 0, 6], "yaw_deg": 0, "pitch_deg": -8},
    ]


def _actor_readback(actor, mapping):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False)
    vertices = actor.bounding_box.get_world_vertices(pose)
    return {"actor_id": actor.id, "blueprint_id": actor.type_id,
            "center_xy_m": [pose.location.x, pose.location.y],
            "body_vertices_m": [[v.x, v.y, v.z] for v in vertices],
            "speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 +
                                   velocity.z ** 2),
            "road_id": None if waypoint is None else waypoint.road_id,
            "lane_id": None if waypoint is None else waypoint.lane_id}


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("Exact materialized output directory required")
    if (output / "capture").exists() or (output / "native_samples.jsonl").exists():
        raise ValueError("Fresh Native attempt required")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in original.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    owned, encoders, logs, queues = [], {}, {}, {}
    encoder_exit_codes = {}
    capture = None
    changed = False
    count = 0
    error = None
    restored = None
    try:
        world = client.generate_opendrive_world(
            open_drive(), carla.OpendriveGenerationParameters(
                vertex_distance=.25, max_road_length=50, wall_height=0,
                additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        library = world.get_blueprint_library()
        emergency_bp = library.find("vehicle.ford.ambulance")
        other_bp = library.find("vehicle.lincoln.mkz_2020")
        emergency_bp.set_attribute("role_name", "c109028_emergency_request")
        other_bp.set_attribute("role_name", "c109028_other_driver")
        ego_wp = mapping.get_waypoint_xodr(1090, -1, 15)
        other_wp = mapping.get_waypoint_xodr(1093, -1, config.get("other_spawn_s_m", 15))
        if ego_wp is None or other_wp is None:
            raise RuntimeError("Original crossroads lanes unavailable")
        ego = world.spawn_actor(emergency_bp, ego_wp.transform)
        owned.append(ego)
        other = world.spawn_actor(other_bp, other_wp.transform)
        owned.append(other)
        if ego.id == other.id:
            raise RuntimeError("Distinct original vehicle actors required")
        _write_new(output / "native-construction-context.json", {
            "case_id": config["case_id"], "ego_blueprint": ego.type_id,
            "other_blueprint": other.type_id,
            "native_road_sha256": hashlib.sha256(
                mapping.to_opendrive().encode()).hexdigest(),
            "ego_start_road_lane": [ego_wp.road_id, ego_wp.lane_id],
            "other_start_road_lane": [other_wp.road_id, other_wp.lane_id],
            "authorization_verified": False,
            "siren_output_verified": False,
            "physical_completion_verified": False})
        for spec in camera_specs():
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            xyz = spec["xyz_m"]
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                carla.Rotation(yaw=spec["yaw_deg"],
                               pitch=spec["pitch_deg"])), attach_to=ego)
            owned.append(camera)
            image_queue = queue.Queue()
            queues[spec["name"]] = image_queue
            camera.listen(image_queue.put)
            log = (output / (spec["name"] + ".encoder.log")).open("x")
            logs[spec["name"]] = log
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-n", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                f'{spec["width"]}x{spec["height"]}', "-r", str(RATE_HZ),
                "-i", "pipe:0", "-an", "-c:v", "ffv1",
                str(output / (spec["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=log)
        capture = PipelineCapture(client, ego, output, config["case_id"],
                                  required_observations=config.get("required_atoms", []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        ego_forward = ego_wp.transform.get_forward_vector()
        other_forward = other_wp.transform.get_forward_vector()
        with (output / "native_samples.jsonl").open("x") as samples, \
             FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(FRAMES):
                plan = request(index, config)
                ego.set_target_velocity(carla.Vector3D(
                    x=2 * ego_forward.x, y=2 * ego_forward.y,
                    z=2 * ego_forward.z))
                speed = plan["other_speed_request_mps"]
                other.set_target_velocity(carla.Vector3D(
                    x=speed * other_forward.x, y=speed * other_forward.y,
                    z=speed * other_forward.z))
                lamps = plan["warning_lamps_requested"]
                ego.set_light_state(carla.VehicleLightState(
                    carla.VehicleLightState.Special1 if lamps
                    else carla.VehicleLightState.NONE))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                row = {"source_kind": "original_native", "native_frame": frame,
                       "time_s": elapsed, "ego": _actor_readback(ego, mapping),
                       "other": _actor_readback(other, mapping),
                       "siren_requested": plan["siren_requested"],
                       "warning_lamps_requested": lamps,
                       "special1_native_readback": bool(
                           ego.get_light_state() & carla.VehicleLightState.Special1),
                       "siren_output_observed": None,
                       "siren_requires_independent_audio": True}
                samples.write(json.dumps(row, allow_nan=False) + "\n")
                capture.capture(frame, elapsed, extra={"c109028_native": row})
                for spec in camera_specs():
                    image = queues[spec["name"]].get(timeout=30)
                    while image.frame < frame:
                        image = queues[spec["name"]].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Original camera/frame join differs")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec["height"], spec["width"], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec["name"]].stdin.write(rgb.tobytes())
                frame_map.append(frame, elapsed)
                count += 1
        if count != FRAMES:
            raise RuntimeError("Incomplete original Native frame window")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name]:
                    raise RuntimeError("Lossless camera encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"restore_error": str(exc)}
        _write_new(output / "native-capture-report.json", {
            "case_id": config["case_id"], "frames": count,
            "expected_frames": FRAMES, "restoration": restored,
            "error": error, "accepted": False,
            "independent_siren_audio_acquired": False,
            "original_dispatch_acquired": False,
            "authorized_emergency_vehicle_verified": False,
            "500_foot_audibility_verified": False})
    if error:
        _write_new(output / "native-run-status.json", {
            "errors": [error], "frames": count,
            "restoration": restored, "encoder_exit_codes": encoder_exit_codes})
        raise RuntimeError("Native capture failed; see native-capture-report.json")
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=count, restoration=restored, errors=[],
                 encoder_exit_codes=encoder_exit_codes,
                 context={"case_id": config["case_id"],
                          "independent_microphone": "pending post-capture source acquisition",
                          "dispatch_authorization": "pending original document review",
                          "physical_or_legal_acceptance": False})
    return {"case_id": config["case_id"], "frames": count,
            "original_camera_capture": True,
            "siren_audio_and_dispatch_pending": True,
            "physical_or_legal_success_claimed": False}
