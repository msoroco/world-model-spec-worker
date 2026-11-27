"""Prospective original railway crossing capture; CARLA imported only on execute.

The reviewed original map must already contain a qualifying railway and two
rail vehicles. This runner never creates decorative tracks or relabels cars.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess

from controller import control
from rail_native_rays import observe
from source_review import ROLES, load as load_review

ASSIGNMENT = "training__C202465__LVMC-11-16-030__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES, RATE_HZ = 600, 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    if (config.get("case_id", "").removeprefix(ASSIGNMENT + "__") not in
            {"selected_bd9b70e5__" + suffix for suffix in (
                "condition_a", "condition_b", "clear_both", "right_obscured",
                "crossing_obscured", "flagman_duty", "signal_inactive",
                "signal_active", "signal_not_visible")}
            or (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("LVMC-11-16-030", "C202465", "motor_vehicle_driver")):
        raise ValueError("exact railway crossing case identity differs")
    if (config.get("rate_hz"), config.get("duration_frames"), config.get("duration_s")) != (20, 600, 30):
        raise ValueError("600 original frames at 20 Hz required")
    if config.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("declared original railway engineering candidate required")
    if config.get("speed_mode") not in ("slower_traversal", "faster_traversal"):
        raise ValueError("exact traversal speed mode required")
    if tuple(c.get("name") for c in config.get("cameras", [])) != CAMERAS:
        raise ValueError("four original crossing cameras required")
    dimensions = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    for c, size in zip(config["cameras"], dimensions):
        if (c.get("width"), c.get("height"), c.get("fps")) != (*size, RATE_HZ):
            raise ValueError("exact four-camera capture and duration plan missing")
        if not isinstance(c.get("mount_xyz_relative_to_crossing_m"), list) or len(c["mount_xyz_relative_to_crossing_m"]) != 3:
            raise ValueError("original crossing camera mount plan missing")
        if any(not isinstance(c.get(key), (int, float)) for key in ("fov_deg", "yaw_deg", "pitch_deg")):
            raise ValueError("original crossing camera orientation plan missing")
    if config.get("feedback_gain") not in (1.0, 1.25) or not config.get("ego_blueprint_filter"):
        raise ValueError("subject controller or blueprint missing")
    if config.get("required_atoms") is None or not isinstance(config["required_atoms"], list):
        raise ValueError("pinned Core atom plan missing")
    return {"case_id": config["case_id"], "frames": FRAMES,
            "simulation_started": False, "physical_acceptance_claimed": False}


def _actor_state(actor, frame):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(pose)
    return {"frame": frame, "actor_id": actor.id, "actor_type_id": actor.type_id,
            "position_m": [pose.location.x, pose.location.y, pose.location.z],
            "velocity_mps": [velocity.x, velocity.y, velocity.z],
            "body_vertices_m": [[p.x, p.y, p.z] for p in vertices]}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / "rail-rays.jsonl").exists():
        raise ValueError("fresh materialized Native attempt required")
    review_dir = os.environ.get("C202465_LVMC_REVIEW_DIR")
    if not review_dir:
        raise ValueError("C202465_LVMC_REVIEW_DIR original review prerequisite missing")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    world = client.get_world()
    road = world.get_map().to_opendrive()
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    reviews = load_review(review_dir, road_sha)
    rail = reviews["railway"]
    approach = reviews["approach"]
    rail_vehicles = []
    for side in ("left", "right"):
        actor = world.get_actor(rail["rail_vehicle_actor_ids"][side])
        if actor is None or not actor.is_alive:
            raise ValueError("reviewed original railway vehicle actor unavailable: " + side)
        rail_vehicles.append({"side": side, "actor": actor})
    saved = snapshot(client)
    if saved["settings"].synchronous_mode:
        raise ValueError("exclusive asynchronous Native world required")
    owned, encoders, camera_queues = [], {}, {}
    changed, completed, errors, codes = False, 0, [], {}
    restoration, failure = {"restored": False}, None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        changed = True
        blueprint = sorted(world.get_blueprint_library().filter(config["ego_blueprint_filter"]),
                           key=lambda b: b.id)[0]
        x, y, z = approach["ego_spawn_xyz_m"]
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=x, y=y, z=z),
            carla.Rotation(yaw=approach["ego_spawn_yaw_deg"])))
        owned.append(ego)
        if not ego.is_alive:
            raise ValueError("original subject motor vehicle failed to spawn")
        (output / "road.xodr").write_text(road)
        copied = output / "original-source-review"
        copied.mkdir(exist_ok=False)
        for role in ROLES:
            for ending in (".json", ".source.txt"):
                shutil.copy2(Path(review_dir) / (role + ending), copied / (role + ending))
        crossing = rail["crossing_xyz_m"]
        for camera in config["cameras"]:
            name = camera["name"]
            dx, dy, dz = camera["mount_xyz_relative_to_crossing_m"]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            bp.set_attribute("sensor_tick", str(1 / RATE_HZ))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=crossing[0]+dx, y=crossing[1]+dy,
                               z=crossing[2]+dz),
                carla.Rotation(yaw=camera["yaw_deg"], pitch=camera["pitch_deg"])))
            owned.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s",
                f"{camera['width']}x{camera['height']}", "-r", str(RATE_HZ),
                "-i", "-", "-frames:v", str(FRAMES), "-c:v", "ffv1", "-level", "1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "rail-rays.jsonl").open("x") as ray_rows, \
                (output / "rail-body.jsonl").open("x") as body_rows, \
                (output / "trace.jsonl").open("x") as trace_rows:
            initial_time = None
            for index in range(FRAMES):
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = control(index, speed, config["speed_mode"],
                                 gain=config["feedback_gain"])
                ego.apply_control(carla.VehicleControl(
                    throttle=target["throttle"], brake=target["brake"],
                    steer=target["steer"]))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise ValueError("original Native world frame mismatch")
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds-initial_time
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < frame:
                        image = q.get(timeout=30)
                    if image.frame != frame:
                        raise ValueError("original camera Native frame mismatch")
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                capture.capture(frame, time_s, extra={"video_frame": index})
                body = _actor_state(ego, frame)
                rays = observe(world, ego, rail_vehicles, rail, carla.Location, frame)
                body_rows.write(json.dumps(body, allow_nan=False) + "\n")
                ray_rows.write(json.dumps(rays, allow_nan=False) + "\n")
                pose = ego.get_transform()
                trace_rows.write(json.dumps({
                    "frame": frame, "time_s": time_s,
                    "position": {"x": pose.location.x, "y": pose.location.y,
                                 "z": pose.location.z}, "speed_mps": speed,
                    "heading_deg": pose.rotation.yaw}, allow_nan=False) + "\n")
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            if codes[name]:
                raise RuntimeError("original camera encoding failed: " + name + error.decode()[-300:])
    except BaseException as exc:
        failure = exc
        errors.append(type(exc).__name__ + ": " + str(exc))
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            try:
                restoration = restore(client, saved)
            except Exception as exc:
                errors.append("world restore: " + str(exc))
        (output / "native-run-status.json").write_text(json.dumps({
            "case_id": config["case_id"], "frames": completed, "errors": errors,
            "restoration": restoration, "encoder_exit_codes": codes,
            "capture_finished": completed == FRAMES and failure is None,
            "physical_acceptance_claimed": False}, indent=2) + "\n")
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError("; ".join(errors))
    seal_capture(output, frames=completed, restoration=restoration, errors=errors,
                 encoder_exit_codes=codes,
                 context={"case_id": config["case_id"],
                          "original_rail_review_sha256": sha(copied / "railway.json"),
                          "exception_duty_and_device_state_pending_saved_review": True,
                          "legal_verdict_claimed": False})
    return {"frames": completed, "original_native_capture": True,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit("--output-dir required")
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
