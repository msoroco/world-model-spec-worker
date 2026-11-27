"""C135702 Native parked-vehicle and highway-obstruction acquisition proposal.

The excavated area is represented by spawned physical barriers. All outcome
fields are original readbacks; the geometry target and traffic controller do
not establish a legal obstruction or a successful physical comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from geometry import EXCAVATION, FRAME_COUNT, PARK_CENTERS_Y, ROAD, check as check_geometry, largest_open_width, open_drive

PREFIX = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver__selected_dacdf461__"
CAMERAS = (("overview", 1920, 1080, -8.0, -15.0, 22.0, -58.0),
           ("approach", 1280, 720, -18.0, -8.0, 9.0, -24.0),
           ("reference_corner", 1280, 720, 2.5, 13.0, 11.0, -46.0),
           ("driver_reference", 1280, 720, 9.0, -9.0, 9.0, -38.0))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path: Path) -> dict:
    cfg = json.loads(path.read_text())
    suffix = cfg.get("case_id", "").removeprefix(PREFIX)
    if suffix not in PARK_CENTERS_Y or cfg["case_id"] != PREFIX + suffix:
        raise ValueError("Exact obstruction comparison case differs")
    if cfg.get("law_id") != "NRS-484B-450-1k" or cfg.get("cell_id") != "C135702" or cfg.get("actor") != "motor_vehicle_driver":
        raise ValueError("Frozen assignment identity differs")
    if (cfg.get("rate_hz"), cfg.get("duration_s"), cfg.get("frames")) != (20, 30, FRAME_COUNT):
        raise ValueError("Four-camera duration differs")
    if cfg.get("park_y_m") != PARK_CENTERS_Y[suffix]:
        raise ValueError("Authored comparison parked position differs")
    if tuple(c["name"] for c in cfg["cameras"]) != tuple(c[0] for c in CAMERAS):
        raise ValueError("Four named camera sources missing")
    if any(c["width"] != spec[1] or c["height"] != spec[2] or c["fps"] != 20
           or not c.get("pose_strategy") or not c.get("fov_deg")
           for c, spec in zip(cfg["cameras"], CAMERAS)):
        raise ValueError("Capture profile differs")
    if cfg.get("physical_acceptance_claimed") is not False or cfg.get("legal_verdict_claimed") is not False:
        raise ValueError("Unobserved outcome asserted")
    if not .1 <= cfg.get("passing_throttle", .25) <= .5:
        raise ValueError("Passing controller throttle outside authored range")
    if not -20 <= cfg.get("brake_station_x_m", -11) <= -8:
        raise ValueError("Passing controller brake station outside authored range")
    if not 0 <= cfg.get("barrier_spawn_z_m", .2) <= 1:
        raise ValueError("Physical barrier spawn elevation outside authored range")
    return {"passed": True, "case_id": cfg["case_id"], "geometry": check_geometry(),
            "native_executed": False, "physical_acceptance_claimed": False}


def body(actor) -> list[float]:
    pose = actor.get_transform()
    points = actor.bounding_box.get_world_vertices(pose)
    if not points:
        raise ValueError("Original Native actor body absent")
    return [min(p.x for p in points), min(p.y for p in points),
            max(p.x for p in points), max(p.y for p in points)]


def reviewed_context(path: Path, case_id: str) -> tuple[dict, str]:
    context = json.loads(path.read_text())
    if context.get("case_id") != case_id or context.get("source_kind") != "reviewed_authority_context":
        raise ValueError("Original case-specific exception source review required")
    flags = context.get("exceptions")
    if flags != {"traffic_conflict": False, "law_direction": False,
                 "police_direction": False, "traffic_device": False}:
        raise ValueError("Comparison cannot preassert an exception")
    reviewed = context.get("exception_source")
    if reviewed != {"traffic_conflict_reviewed": True, "law_direction_reviewed": True,
                    "police_direction_reviewed": True, "traffic_device_reviewed": True}:
        raise ValueError("Exception source review incomplete")
    records = context.get("source_records")
    if not isinstance(records, dict) or set(records) != set(flags):
        raise ValueError("Separate original authority records required")
    for name, item in records.items():
        relative = Path(item.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Invalid authority source path: " + name)
        source = (path.parent / relative).resolve()
        if path.parent.resolve() not in source.parents or not source.is_file() or sha(source) != item.get("sha256"):
            raise ValueError("Missing or changed authority source: " + name)
    return context, sha(path)


def barrier_blueprint(library):
    candidates = sorted((b for b in library.filter("static.prop.*")
                         if any(token in b.id.lower() for token in ("barrier", "roadblock", "construction"))),
                        key=lambda b: b.id)
    if not candidates:
        raise ValueError("No eligible physical excavation barrier asset in Native library")
    return candidates[0]


def run(path: Path, output: Path, context_path: Path, host: str, port: int) -> dict:
    cfg = json.loads(path.read_text())
    check(path)
    context, context_sha = reviewed_context(context_path, cfg["case_id"])
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import restore, snapshot

    if output.exists():
        raise ValueError("Use a fresh original Native attempt directory")
    client = carla.Client(host, port)
    client.set_timeout(180)
    original_world = client.get_world()
    saved_world = snapshot(client)
    if original_world.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in original_world.get_actors()):
        raise ValueError("Exclusive idle Native world required")
    output.mkdir(parents=True)
    for item in context["source_records"].values():
        relative = Path(item["path"])
        copied = output / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(context_path.parent / relative, copied)
        if sha(copied) != item["sha256"]:
            raise ValueError("Copied original authority source changed")
    actors, cameras, encoders = [], {}, {}
    capture = None
    changed = False
    encoder_exits = {}
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        waypoint = world.get_map().get_waypoint(carla.Location(x=2.5, y=cfg["park_y_m"], z=1),
                                                project_to_road=True,
                                                lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1:
            raise ValueError("Native narrow-highway lane readback differs")
        library = world.get_blueprint_library()
        vehicle_bp = library.find(cfg["vehicle_blueprint_id"])
        ego = world.try_spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=2.5, y=cfg["park_y_m"], z=1.1), carla.Rotation(yaw=0)))
        other = world.try_spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-40, y=-.3, z=1.1), carla.Rotation(yaw=0)))
        if ego is None or other is None:
            raise ValueError("Native parked or passing vehicle spawn failed")
        actors.extend((ego, other))
        barrier_bp = barrier_blueprint(library)
        for x in (1.0, 2.5, 4.0):
            obstacle = world.try_spawn_actor(barrier_bp, carla.Transform(
                carla.Location(x=x, y=2.2, z=cfg.get("barrier_spawn_z_m", .2)),
                carla.Rotation(yaw=0)))
            if obstacle is None:
                raise ValueError("Physical excavation barrier spawn failed")
            actors.append(obstacle)
        barrier_bodies = [body(actor) for actor in actors[2:]]
        obstruction = [min(b[0] for b in barrier_bodies), min(b[1] for b in barrier_bodies),
                       max(b[2] for b in barrier_bodies), max(b[3] for b in barrier_bodies)]
        if not (ROAD[0] < obstruction[0] < obstruction[2] < ROAD[2] and
                ROAD[1] < obstruction[1] < obstruction[3] < ROAD[3]):
            raise ValueError("Original barrier bodies miss surveyed highway")
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 85), ("sensor_tick", .05)):
                bp.set_attribute(key, str(value))
            heading = math.degrees(math.atan2(-y, 2.5 - x))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch, yaw=heading)))
            actors.append(sensor)
            received = queue.Queue()
            sensor.listen(received.put)
            cameras[name] = received
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", "20", "-i", "-", "-frames:v", str(FRAME_COUNT), "-c:v", "ffv1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, ego, output, cfg["case_id"], required_observations=[])
        with (output / "native_samples.jsonl").open("x") as samples, \
                (output / "camera-frames.jsonl").open("x") as camera_rows, \
                FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(FRAME_COUNT):
                ego.apply_control(carla.VehicleControl(hand_brake=True, brake=1))
                ego_box = body(ego)
                width = other.bounding_box.extent.y * 2
                opening = largest_open_width(ROAD, [tuple(obstruction), tuple(ego_box)])
                other_x = other.get_transform().location.x
                too_narrow = opening < width + .2
                brake = 1.0 if too_narrow and other_x >= cfg.get("brake_station_x_m", -11) else 0.0
                other.apply_control(carla.VehicleControl(throttle=0.0 if brake else cfg.get("passing_throttle", .25),
                                                         brake=brake))
                native_frame = world.tick()
                ego_velocity, other_velocity = ego.get_velocity(), other.get_velocity()
                row = {"native_frame": native_frame, "time_s": index / 20,
                       "road_xy_m": list(ROAD), "obstruction_xy_m": obstruction,
                       "obstruction_kind": "physical_obstruction", "ego_body_xy_m": body(ego),
                       "ego_speed_m_s": math.hypot(ego_velocity.x, ego_velocity.y),
                       "passing_body_xy_m": body(other),
                       "passing_speed_m_s": math.hypot(other_velocity.x, other_velocity.y),
                       "exceptions": context["exceptions"],
                       "exception_source": context["exception_source"],
                       "context_sha256": context_sha,
                       "barrier_actor_ids": [a.id for a in actors[2:5]],
                       "other_actor_id": other.id,
                       "controller_clearance_m": opening,
                       "controller_brake_command": brake,
                       "source_kind": "original_native"}
                samples.write(json.dumps(row, allow_nan=False) + "\n")
                capture.capture(native_frame, index / 20, extra={"c135702_obstruction": row})
                joined = {}
                for name, received in cameras.items():
                    image = received.get(timeout=30)
                    while image.frame < native_frame:
                        image = received.get(timeout=30)
                    if image.frame != native_frame:
                        raise ValueError("Original camera frame join differs")
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = image.frame
                    camera_rows.write(json.dumps({"frame": index, "native_frame": native_frame,
                                                 "camera": name, "source_kind": "original_native",
                                                 "rgb_sha256": hashlib.sha256(image.raw_data).hexdigest()}) + "\n")
                frame_map.append(native_frame, index / 20, camera_native_frames=joined)
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + ".mkv")).is_file():
                raise ValueError("Original camera encoding failed: " + name + error.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        (output / "road.xodr").write_text(open_drive())
        (output / "exception-context.json").write_text(json.dumps(context, sort_keys=True) + "\n")
        (output / "obstruction-inventory.json").write_text(json.dumps({
            "source_kind": "original_native", "obstruction_kind": "physical_obstruction",
            "road_xy_m": ROAD,
            "obstruction_xy_m": obstruction, "barrier_actor_ids": [a.id for a in actors[2:5]],
            "parked_actor_id": ego.id, "passing_actor_id": other.id,
            "barrier_blueprint_id": barrier_bp.id, "physical_cause_confirmed": False,
            "legal_verdict_claimed": False}, sort_keys=True) + "\n")
        return {"frames": FRAME_COUNT, "camera_names": list(cameras),
                "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored = restore(client, saved_world)
            if capture is None and len(encoder_exits) == 4 and all(code == 0 for code in encoder_exits.values()):
                seal_capture(output, frames=FRAME_COUNT, restoration=restored,
                             errors=[], encoder_exit_codes=encoder_exits,
                             context={"case_id": cfg["case_id"]})
                record_native_exit(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.config)))
    else:
        if args.output_dir is None or args.context is None:
            parser.error("Original capture requires a fresh output and reviewed source context")
        print(json.dumps(run(args.config, args.output_dir, args.context, args.host, args.port)))
