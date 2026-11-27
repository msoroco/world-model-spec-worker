"""Source-gated parked-vehicle lamp capture; physical visibility stays unverified."""
import argparse
import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
from pathlib import Path

ASSIGNMENT = "training__C183085__NRS-484D-165-3__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FROZEN = {"layout": "paved_shoulder", "maneuver": "stop_stand", "control": "other_vehicle"}


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    require(config.get("case_id", "").startswith(ASSIGNMENT + "__") and
            config.get("law_id") == "NRS-484D-165-3" and
            config.get("cell_id") == "C183085" and
            config.get("actor") == "motor_vehicle_driver" and
            config.get("frozen_cell") == FROZEN, "Wrong case or frozen cell")
    require(config.get("frames") == 600 and config.get("rate_hz") == 20 and
            config.get("duration_s") == 30, "Full stopped interval required")
    require(config.get("lamp_command") in ("display", "omit") and
            config.get("optical_target_kind") in ("ambient_reveal", "front_white_or_amber",
            "rear_red", "none"), "Lamp or optical target missing")
    require(config.get("physical_completion") == {} and
            config.get("legal_verdict") is None, "Unverified outcome claimed")
    cameras = config.get("cameras", [])
    require(tuple(c.get("name") for c in cameras) == VIEWS, "Four cameras required")
    for camera in cameras:
        require(camera.get("fps") == 20 and camera.get("width", 0) >= 1280 and
                camera.get("height", 0) >= 720 and
                len(camera.get("location_xyz_m", [])) == 3 and
                len(camera.get("rotation_pyr_deg", [])) == 3,
                "Camera profile or pose missing")
    require(cameras[0]["width"] == 1920 and cameras[0]["height"] == 1080,
            "Overview profile changed")
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "camera_ids": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def survey_source(path, config):
    source = json.loads(Path(path).read_text())
    require(source.get("source_kind") == "original_native_shoulder_lighting_survey" and
            source.get("map_name") and source.get("highway_identity_source") and
            source.get("adjacent_paved_shoulder_source") and
            source.get("passing_lane_source") and
            source.get("passing_traffic_side") in ("left", "right") and
            source.get("lighting_hours_source") and
            source.get("civil_time_source") and
            source.get("ambient_reveal_protocol_source") and
            source.get("front_lamp_protocol_source") and
            source.get("rear_lamp_protocol_source") and
            len(source.get("shoulder_xyz_m", [])) == 3 and
            isinstance(source.get("shoulder_yaw_deg"), (int, float)) and
            isinstance(source.get("passing_vehicle_spawn_index"), int),
            "Original shoulder, lighting-hour and optical source survey missing")
    require(source.get("optical_target_kind") == config["optical_target_kind"],
            "Optical target survey differs")
    require(source.get("target_distance_ft") == config.get("target_distance_ft"),
            "Optical target distance differs")
    return source


def execute(config, output_dir, survey_path, host, port):
    check(config)
    survey_path = survey_path or os.environ.get("C183085_SHOULDER_SURVEY")
    require(survey_path, "Original shoulder lighting survey required")
    source = survey_source(survey_path, config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    require(output.is_dir() and (output / "config.json").is_file(),
            "Use fresh exact-case materialized output")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoder_codes, errors = [], [], {}, []
    images = queue.Queue()
    restoration = None
    try:
        require(world.get_map().name == source["map_name"], "Survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = source["passing_vehicle_spawn_index"]
        require(0 <= index < len(spawns), "Surveyed passing-lane spawn unavailable")
        sx, sy, sz = source["shoulder_xyz_m"]
        shoulder_location = carla.Location(x=sx, y=sy, z=sz)
        waypoint = world.get_map().get_waypoint(shoulder_location,
            project_to_road=False, lane_type=carla.LaneType.Shoulder)
        require(waypoint is not None, "Surveyed pose is not a mapped shoulder")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(
            config["vehicle_blueprint"]), carla.Transform(shoulder_location,
            carla.Rotation(yaw=source["shoulder_yaw_deg"])))
        require(ego is not None, "Surveyed shoulder pose occupied")
        actors.append(ego)
        passing = world.try_spawn_actor(world.get_blueprint_library().find(
            config["vehicle_blueprint"]), spawns[index])
        require(passing is not None and passing.id != ego.id,
                "Passing-traffic reference vehicle unavailable")
        actors.append(passing)
        shutil.copyfile(survey_path, output / "shoulder_lighting_survey.json")
        lamp_state = carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam
        ego.set_light_state(carla.VehicleLightState(
            lamp_state if config["lamp_command"] == "display" else 0))
        for camera in config["cameras"]:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            x, y, z = camera["location_xyz_m"]
            pitch, yaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "shoulder-lamp-trace.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                ego.apply_control(carla.VehicleControl(throttle=0, brake=1,
                                                       hand_brake=True))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                velocity = ego.get_velocity()
                state = int(ego.get_light_state())
                trace.write(json.dumps({"source_kind": "original_native_observation",
                    "frame": frame, "native_frame": native_frame, "video_frame": frame,
                    "time_s": frame / 20, "ego_actor_id": ego.id,
                    "ego_speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                    "vehicle_light_state_bits": state,
                    "position_commanded": bool(state & int(carla.VehicleLightState.Position)),
                    "low_beam_commanded": bool(state & int(carla.VehicleLightState.LowBeam)),
                    "front_white_or_amber_visible_from_ft": None,
                    "rear_red_visible_from_ft": None,
                    "ambient_reveal_distance_ft": None,
                    "passing_traffic_side": source["passing_traffic_side"]}) + "\n")
        for name in VIEWS:
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-framerate", "20", "-start_number", "0", "-i",
                       str(output / name / "%06d.png"), "-frames:v", "600",
                       "-an", "-c:v", "ffv1", "-threads", "1",
                       str(output / (name + ".mkv"))]
            process = subprocess.run(command, timeout=300, capture_output=True, text=True)
            encoder_codes[name] = process.returncode
            require(process.returncode == 0, "Camera encode failed: " + name)
    except BaseException as error:
        errors.append({"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                errors.append("sensor_stop: " + str(error))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append("actor_destroy: " + str(error))
        try:
            restoration = restore(client, original)
        except BaseException as error:
            errors.append("world_restore: " + str(error))
        if errors:
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": errors, "restoration": restoration,
                "physical_acceptance_claimed": False}) + "\n")
    require(not errors, "Native capture or cleanup failed")
    seal_capture(output, frames=600, restoration=restoration, errors=[],
                 encoder_exit_codes=encoder_codes, context={"shoulder_survey_sha256":
                 hashlib.sha256((output / "shoulder_lighting_survey.json").read_bytes()).hexdigest()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--shoulder-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "Output directory required")
        execute(cfg, args.output_dir, args.shoulder_survey, args.host, args.port)
