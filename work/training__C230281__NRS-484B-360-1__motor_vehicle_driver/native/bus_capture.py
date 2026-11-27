"""Prospective source-preserving capture for the three 55 mph bus probes.

The bus design, pupils and trip purpose require independent original review.
This module makes no physical or legal finding and imports CARLA only at launch.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess


AID = "training__C230281__NRS-484B-360-1__motor_vehicle_driver"
SPEEDS = (53, 55, 57)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 600
RATE = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_id(speed):
    require(type(speed) is int and speed in SPEEDS, "Unexpected school-bus speed case")
    return f"{AID}__{speed}"


def capture_plan(speed):
    return {"assignment_id": AID, "case_id": case_id(speed), "cell_id": "C230281",
            "actor": "motor_vehicle_driver", "frozen_cell": {
                "layout": "road", "maneuver": "travel", "control": "school_bus"},
            "requested_speed_mph": speed, "rate_hz": RATE, "frames": FRAMES,
            "duration_s": 30, "camera_names": list(CAMERAS),
            "camera_sizes": CAMERA_SIZES, "source_kind": "prospective_native_capture",
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def validate_survey(survey):
    require(survey.get("source_kind") == "original_native_school_bus_route_survey",
            "An original route survey is required")
    require(survey.get("assignment_id") == AID and survey.get("cell_id") == "C230281",
            "Survey assignment or cell differs")
    require(survey.get("layout") == "road" and survey.get("maneuver") == "travel"
            and survey.get("control") == "school_bus", "Frozen cell differs")
    require(isinstance(survey.get("map_name"), str) and survey["map_name"], "Map source absent")
    require(isinstance(survey.get("bus_blueprint"), str) and survey["bus_blueprint"],
            "Bus blueprint source absent")
    require(isinstance(survey.get("bus_design_source"), str) and survey["bus_design_source"],
            "Bus design source absent")
    require(isinstance(survey.get("route_source"), str) and survey["route_source"],
            "Route source absent")
    require(type(survey.get("clear_road_length_m")) in (int, float)
            and survey["clear_road_length_m"] >= 900, "900 m clear road survey required")
    transform = survey.get("spawn_xyz_yaw_deg")
    require(isinstance(transform, list) and len(transform) == 4
            and all(type(x) in (int, float) and math.isfinite(x) for x in transform),
            "Surveyed spawn transform invalid")
    return survey


def preflight():
    plans = [capture_plan(speed) for speed in SPEEDS]
    require(len({plan["case_id"] for plan in plans}) == 3, "Duplicate exact case")
    return {"plans": plans, "simulation_started": False,
            "original_bus_or_pupils_confirmed": False}


def _camera_specs():
    return (("overview", (2.0, 0.0, 2.4), (0, 0, 0)),
            ("approach", (-2.0, 0.0, 2.4), (0, 180, 0)),
            ("reference_corner", (0.0, -0.35, 2.0), (0, -90, 0)),
            ("driver_reference", (0.0, 0.35, 2.0), (0, 90, 0)))


def run(speed, survey_path, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import restore, snapshot

    plan = capture_plan(speed)
    survey_path = Path(survey_path)
    survey = validate_survey(json.loads(survey_path.read_text()))
    output = Path(output_dir).resolve()
    require(not any((output / name).exists() for name in
                    ("video_frames.jsonl", "bus_motion.jsonl", "capture-seal.json")),
            "Retain prior Native attempt; use a fresh output")
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior = snapshot(client)
    world = client.get_world()
    sensors, encoders = {}, {}
    vehicle = None
    core = None
    restored = None
    try:
        require(world.get_map().name == survey["map_name"], "Native map differs from survey")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprint = library.find(survey["bus_blueprint"])
        require(blueprint is not None, "Surveyed bus asset unavailable")
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        vehicle = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(vehicle is not None, "Surveyed bus spawn unavailable")
        incoming = {}
        for name, location, rotation in _camera_specs():
            camera_bp = library.find("sensor.camera.rgb")
            width, height = CAMERA_SIZES[name]
            camera_bp.set_attribute("image_size_x", str(width))
            camera_bp.set_attribute("image_size_y", str(height))
            camera_bp.set_attribute("sensor_tick", "0.0")
            sensor = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(*location), carla.Rotation(*rotation)), attach_to=vehicle)
            sensors[name] = sensor
            incoming[name] = queue.Queue()
            sensor.listen(incoming[name].put)
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "bgra",
                "-video_size", f"{width}x{height}", "-framerate", "20", "-i", "-",
                "-frames:v", "600", "-c:v", "ffv1", str(output / f"{name}.mkv")],
                stdin=subprocess.PIPE)
        core = PipelineCapture(client, vehicle, output, plan["case_id"],
                               required_observations=[])
        first_elapsed = None
        with (output / "video_frames.jsonl").open("x") as frame_file, \
                (output / "bus_motion.jsonl").open("x") as motion_file:
            for i in range(FRAMES):
                velocity = vehicle.get_velocity()
                observed_mps = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                error = speed * 0.44704 - observed_mps
                throttle = min(0.75, max(0.0, 0.2 + 0.1 * error))
                brake = min(0.6, max(0.0, -0.12 * error))
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake,
                                                            steer=0.0))
                native = world.tick()
                snap = world.get_snapshot()
                require(native == snap.frame, "Native tick/frame mismatch")
                if first_elapsed is None:
                    first_elapsed = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds - first_elapsed
                require(abs(elapsed - i / RATE) <= .005, "Native sample cadence differs")
                core.capture(native, elapsed, extra={"bus_actor_id": vehicle.id})
                location = vehicle.get_location()
                waypoint = world.get_map().get_waypoint(location, project_to_road=False)
                require(waypoint is not None and not waypoint.is_junction,
                        "Bus left the surveyed travel lane")
                hashes = {}
                for name in CAMERAS:
                    image = incoming[name].get(timeout=30)
                    require(image.frame == native, "Camera/Native frame mismatch: " + name)
                    hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                    encoders[name].stdin.write(image.raw_data)
                frame_file.write(json.dumps({"video_frame": i, "native_frame": native,
                    "time_s": i / RATE, "camera_rgb_sha256": hashes}, allow_nan=False) + "\n")
                velocity = vehicle.get_velocity()
                motion_file.write(json.dumps({"video_frame": i, "native_frame": native,
                    "velocity_mps": [velocity.x, velocity.y, velocity.z],
                    "position_xyz_m": [location.x, location.y, location.z],
                    "road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
                    "source_kind": "original_native_velocity", "bus_actor_id": vehicle.id,
                    "requested_speed_mph": speed}, allow_nan=False) + "\n")
        for process in encoders.values():
            process.stdin.close()
            require(process.wait(timeout=120) == 0, "Camera encoder failed")
        for name in CAMERAS:
            count = subprocess.check_output([
                "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_frames", "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(output / f"{name}.mkv")], text=True, timeout=120).strip()
            require(count == "600", "Original camera full decode differs: " + name)
        core.close(confirmed=True)
        core = None
        source_names = ("video_frames.jsonl", "bus_motion.jsonl", *
                        (f"{name}.mkv" for name in CAMERAS))
        (output / "bus_capture_context.json").write_text(json.dumps({
            "assignment_id": AID, "case_id": plan["case_id"],
            "survey_sha256": digest(survey_path), "bus_actor_id": vehicle.id,
            "bus_blueprint_requested": survey["bus_blueprint"],
            "bus_design_source": survey["bus_design_source"],
            "route_source": survey["route_source"],
            "source_sha256": {name: digest(output / name) for name in source_names},
            "school_bus_confirmed": False, "pupils_aboard_confirmed": False,
            "trip_purpose_confirmed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}, sort_keys=True) + "\n")
        for sensor in sensors.values():
            sensor.stop()
            sensor.destroy()
        sensors.clear()
        vehicle.destroy()
        vehicle = None
        restored = restore(client, prior)
        seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode
                                         for name, process in encoders.items()},
                     context={"case_id": plan["case_id"], "physical_acceptance_claimed": False})
        return {"case_id": plan["case_id"], "frames": FRAMES,
                "original_native_capture_saved": True, "physical_acceptance_claimed": False}
    finally:
        if core is not None:
            core.close(confirmed=False)
        for sensor in sensors.values():
            sensor.stop()
            sensor.destroy()
        if vehicle is not None:
            vehicle.destroy()
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        if restored is None:
            restore(client, prior)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", type=int, choices=SPEEDS)
    parser.add_argument("--route-survey")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config_path = Path("config.json")
    selected = None
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        selected = config.get("requested_speed_mph")
        require(config.get("case_id") == case_id(selected)
                and config.get("assignment_id") == AID,
                "Materialized speed case identity differs")
        if args.case is not None:
            require(args.case == selected, "CLI case differs from materialized case")
    if args.check:
        report = preflight()
        report["materialized_case_id"] = case_id(selected) if selected is not None else None
        print(json.dumps(report, sort_keys=True))
    else:
        speed = args.case if args.case is not None else selected
        survey = args.route_survey or os.environ.get("SCENARIO_BUS_ROUTE_SURVEY")
        require(speed is not None and survey and args.output_dir,
                "Case, original route survey and output directory required")
        print(json.dumps(run(speed, survey, args.output_dir,
                             args.host, args.port), sort_keys=True))
