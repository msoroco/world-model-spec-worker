"""Original Native roundabout source acquisition; physical results are unclaimed."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

RATE = 20
FRAMES = 600
RELEASE = {"probe_a": 1, "probe_b": -1}
CAMERAS = (("overview", 1920, 1080, 22, 0, 55, -90),
           ("approach", 1280, 720, 22, -35, 17, -35),
           ("reference_corner", 1280, 720, 45, 0, 18, -45),
           ("driver_reference", 1280, 720, 22, -16, 8, -20))


def check(config=None):
    if FRAMES != RATE * 30 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError("Thirty seconds and four source cameras required")
    if config is not None:
        assignment = "training__C238396__LVMC-11-43-010-A__motor_vehicle_driver"
        case_ids = {assignment + "__selected_a60a4f45__" + condition: release
                    for condition, release in RELEASE.items()}
        case_id = config.get("case_id")
        if case_id not in case_ids or config.get("selected_case_id") != case_id:
            raise ValueError("Exact case identity differs")
        if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
                "LVMC-11-43-010-A", "C238396", "motor_vehicle_driver"):
            raise ValueError("Law/cell/actor identity differs")
        if (config.get("rate_hz"), config.get("duration_s"),
                config.get("duration_frames")) != (20, 30, 600):
            raise ValueError("Full 30-second source window required")
        if [c.get("name") for c in config.get("cameras", [])] != [c[0] for c in CAMERAS]:
            raise ValueError("Four source cameras required")
        if config.get("requested_direction") != ("counterclockwise" if case_ids[case_id] == 1 else "clockwise"):
            raise ValueError("Controlled translational direction differs")
        if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
            raise ValueError("Diagnostic must not claim physical or legal result")
        steering = {"primary": (1.3, .75), "fallback1": (2.0, .95)}
        if (config.get("steer_gain"), config.get("max_steer")) != steering.get(
                config.get("candidate_id")):
            raise ValueError("Steering candidate knobs differ")
    return {"frames": FRAMES, "rate_hz": RATE, "camera_names": [c[0] for c in CAMERAS],
            "geometry": geometry_check(), "native_executed": False,
            "physical_completion_claimed": False}


def target(role, t, sign):
    if role == "ego":
        angle, radius, speed = -math.pi / 2 + sign * 4.0 * t / 16.75, 16.75, 4.0
    else:
        angle, radius, speed = math.pi / 2 + 3.0 * t / 20.25, 20.25, 3.0
    return (22 + radius * math.cos(angle), radius * math.sin(angle)), speed


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def control(actor, xy, wanted_speed, carla, gain=1.3, max_steer=.75):
    pose = actor.get_transform()
    wanted_yaw = math.atan2(xy[1] - pose.location.y, xy[0] - pose.location.x)
    error = math.atan2(math.sin(wanted_yaw - math.radians(pose.rotation.yaw)),
                       math.cos(wanted_yaw - math.radians(pose.rotation.yaw)))
    delta = wanted_speed - speed(actor)
    return carla.VehicleControl(throttle=max(0, min(.55, delta * .24)),
                                brake=max(0, min(1, -delta * .42)),
                                steer=max(-max_steer, min(max_steer, error * gain)))


def survey(world, carla):
    samples = []
    for road, x, y in ((21, 22, -15), (23, 22, 15)):
        wp = world.get_map().get_waypoint(carla.Location(x=x, y=y, z=1),
            project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != road:
            raise RuntimeError(f"Native road {road} waypoint readback missing")
        samples.append({"road_id": wp.road_id, "lane_id": wp.lane_id,
                        "x_m": wp.transform.location.x, "y_m": wp.transform.location.y})
    return samples


def execute(output_dir, condition, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    check(json.loads(Path("config.json").read_text()))
    if condition not in RELEASE:
        raise ValueError("Unknown exact condition")
    output = Path(output_dir).resolve()
    if any((output / p).exists() for p in ("video_frames.jsonl", "native-raw-actors.jsonl")):
        raise ValueError("Original Native source path already occupied")
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    if saved["settings"].synchronous_mode or any(a.type_id.startswith(
            ("vehicle.", "walker.", "sensor.", "controller.")) for a in client.get_world().get_actors()):
        raise RuntimeError("Requires exclusive idle asynchronous Native world")
    config = json.loads(Path("config.json").read_text())
    owned, encoders, cameras = [], {}, {}
    changed = False
    failure, errors, encoder_codes = None, [], {}
    restoration = {"restored": False}
    completed = 0
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        map_rows = survey(world, carla)
        output.mkdir(parents=True, exist_ok=True)
        (output / "road.xodr").write_text(world.get_map().to_opendrive())
        (output / "roundabout-map-readback.json").write_text(json.dumps({
            "source_kind": "native_map_readback", "samples": map_rows,
            "full_boundary_review_complete": False}, indent=2) + "\n")
        blueprints = sorted(world.get_blueprint_library().filter("vehicle.*"), key=lambda b: b.id)
        if len(blueprints) < 2:
            raise RuntimeError("Two vehicle blueprints required")
        starts = {"ego": (22, -16.75, 0), "other": (42.25, 0, 90)}
        actors = {}
        for bp, (role, (x, y, yaw)) in zip(blueprints, starts.items()):
            bp.set_attribute("role_name", "c238396_" + role)
            actor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=.6), carla.Rotation(yaw=yaw)))
            owned.append(actor)
            actors[role] = actor
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("fov", "85")
            bp.set_attribute("sensor_tick", str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            cameras[name] = frames
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", str(RATE), "-i", "-", "-frames:v", str(FRAMES),
                "-c:v", "ffv1", "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with PipelineCapture(client, actors["ego"], output, config["case_id"],
                required_observations=config.get("required_atoms", [])) as capture, (
                FrameMap(output / "video_frames.jsonl")) as frame_map, (
                output / "native-raw-actors.jsonl").open("x") as raw, (
                output / "control-intent.jsonl").open("x") as intent, (
                output / "trace.jsonl").open("x") as trace:
            first_elapsed = None
            for frame in range(FRAMES):
                commands = {}
                for role, actor in actors.items():
                    xy, goal_speed = target(role, frame / RATE, RELEASE[condition])
                    command = control(actor, xy, goal_speed, carla,
                                      gain=config["steer_gain"],
                                      max_steer=config["max_steer"])
                    actor.apply_control(command)
                    commands[role] = {"target_xy_m": xy, "target_speed_mps": goal_speed,
                                      "throttle": command.throttle, "brake": command.brake,
                                      "steer": command.steer}
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError("Native snapshot/frame identity differs")
                absolute = snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute
                elapsed = absolute - first_elapsed
                observed = []
                for role, actor in actors.items():
                    pose = actor.get_transform()
                    box = actor.bounding_box.extent
                    wp = world.get_map().get_waypoint(pose.location,
                        project_to_road=True, lane_type=carla.LaneType.Driving)
                    observed.append({"role": role, "actor_id": actor.id,
                        "blueprint_id": actor.type_id, "x_m": pose.location.x,
                        "y_m": pose.location.y, "yaw_deg": pose.rotation.yaw,
                        "speed_mps": speed(actor), "bbox_half_length_m": box.x,
                        "bbox_half_width_m": box.y,
                        "road_id": wp.road_id if wp else None,
                        "lane_id": wp.lane_id if wp else None})
                mapped = {}
                for name, frames in cameras.items():
                    image = frames.get(timeout=30)
                    while image.frame < native_frame:
                        image = frames.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera frame join failed: " + name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, elapsed, camera_native_frames=mapped)
                capture.capture(native_frame, elapsed, extra={"video_frame": frame})
                case_id = config["case_id"]
                raw.write(json.dumps({"video_frame": frame, "native_frame": native_frame,
                    "time_s": elapsed, "native_elapsed_seconds": absolute,
                    "case_id": case_id, "actors": observed}) + "\n")
                intent.write(json.dumps({"video_frame": frame, "native_frame": native_frame,
                    "time_s": elapsed, "controls": commands}) + "\n")
                ego = next(a for a in observed if a["role"] == "ego")
                trace.write(json.dumps({"frame": native_frame, "time_s": elapsed,
                    "position": {"x": ego["x_m"], "y": ego["y_m"], "z": 0},
                    "heading_deg": ego["yaw_deg"], "speed_mps": ego["speed_mps"],
                    "control": commands["ego"]}) + "\n")
                completed += 1
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            if encoder_codes[name] or not (output / (name + ".mkv")).is_file():
                raise RuntimeError(f"Camera encoding failed: {name}: {error.decode()[-400:]}")
    except BaseException as error:
        failure = error
        errors.append(f"{type(error).__name__}: {error}")
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
            except Exception as error:
                errors.append(f"actor destroy: {error}")
        if changed:
            try:
                restoration = restore(client, saved)
            except Exception as error:
                errors.append(f"world restore: {error}")
        if output.exists():
            (output / "native-run-status.json").write_text(json.dumps({
                "case_id": config["case_id"], "frames": completed,
                "errors": errors, "restoration": restoration,
                "encoder_exit_codes": encoder_codes,
                "capture_finished": completed == FRAMES and failure is None,
                "acceptance_claimed": False}, indent=2) + "\n")
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError("; ".join(errors))
    seal_capture(output, frames=completed, restoration=restoration, errors=errors,
                 encoder_exit_codes=encoder_codes,
                 context={"case_id": config["case_id"],
                          "source": "original Native CARLA capture",
                          "legal_verdict": None})
    return {"native_frames": completed, "camera_names": list(cameras),
            "actor_roles": list(actors), "map_readback": map_rows,
            "physical_completion_claimed": False, "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--condition", choices=tuple(RELEASE))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.output_dir:
            raise SystemExit("--output-dir required")
        condition = args.condition or json.loads(Path("config.json").read_text())["condition"]
        print(json.dumps(execute(args.output_dir, condition, args.host, args.port)))
