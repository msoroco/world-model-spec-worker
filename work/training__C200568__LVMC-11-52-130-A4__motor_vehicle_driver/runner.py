"""Source-gated Native hydrant parking capture proposal.

The offline check validates the exact construction. A Native run needs an
independent map, parking-permission and hydrant survey; no fixture substitutes
for those sources or proves a statutory exception.
"""

import argparse
import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
import traceback
from pathlib import Path

ASSIGNMENT = "training__C200568__LVMC-11-52-130-A4__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FROZEN = {"layout": "public_access_premises", "maneuver": "park", "control": "fire_hydrant"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    require(config.get("case_id", "").startswith(ASSIGNMENT + "__") and
            config.get("law_id") == "LVMC-11-52-130-A4" and
            config.get("cell_id") == "C200568" and
            config.get("actor") == "motor_vehicle_driver" and
            config.get("frozen_cell") == FROZEN, "Wrong assignment or frozen cell")
    require(config.get("frames") == 600 and config.get("rate_hz") == 20 and
            config.get("duration_s") == 30, "Full source window required")
    require(config.get("parking_permission") in ("parallel_permitted", "angle_permitted",
            "no_parking_permitted"), "Parking permission missing")
    require(config.get("requested_clearance_ft") in (14.5, 15, 15.5, 19.5, 20,
            20.5, 21, 22), "Requested clearance unsupported")
    require(config.get("exception_context") in ("none", "traffic_conflict",
            "other_law", "officer_or_device"), "Exception declaration missing")
    require(config.get("physical_completion") == {} and
            config.get("legal_verdict") is None, "Unverified outcome claimed")
    cameras = config.get("cameras", [])
    require(tuple(camera.get("name") for camera in cameras) == VIEWS,
            "Four named cameras required")
    for camera in cameras:
        require(camera.get("fps") == 20 and camera.get("width", 0) >= 1280 and
                camera.get("height", 0) >= 720 and
                len(camera.get("location_xyz_m", [])) == 3 and
                len(camera.get("rotation_pyr_deg", [])) == 3,
                "Camera capability or pose missing")
    require(cameras[0]["width"] == 1920 and cameras[0]["height"] == 1080,
            "Overview capability changed")
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "source_views": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def survey_source(path, config):
    source = json.loads(Path(path).read_text())
    require(source.get("source_kind") == "original_native_hydrant_survey" and
            source.get("map_name") and source.get("premises_access_source") and
            source.get("parking_permission_source") and
            source.get("parking_permission") == config["parking_permission"] and
            source.get("hydrant_identity_source") and
            len(source.get("hydrant_xyz_m", [])) == 3 and
            source.get("vehicle_spawn_index") is not None and
            source.get("distance_uncertainty_ft", -1) >= 0,
            "Original hydrant, access and permission survey missing")
    return source


def execute(config, output_dir, survey_path, host, port):
    check(config)
    survey_path = survey_path or os.environ.get("C200568_HYDRANT_SURVEY")
    require(survey_path, "Original hydrant survey required")
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
    actors, sensors, errors, encoder_codes = [], [], [], {}
    images = queue.Queue()
    restoration = None
    try:
        require(world.get_map().name == source["map_name"], "Survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = source["vehicle_spawn_index"]
        require(0 <= index < len(spawns), "Vehicle spawn unavailable")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(
            config["vehicle_blueprint"]), spawns[index])
        require(ego is not None, "Vehicle spawn occupied")
        actors.append(ego)
        hydrant_name = source.get("hydrant_blueprint", "static.prop.firehydrant")
        hydrant_bp = world.get_blueprint_library().find(hydrant_name)
        hx, hy, hz = source["hydrant_xyz_m"]
        hydrant = world.try_spawn_actor(hydrant_bp, carla.Transform(
            carla.Location(x=hx, y=hy, z=hz)))
        require(hydrant is not None, "Hydrant placement failed")
        actors.append(hydrant)
        shutil.copyfile(survey_path, output / "hydrant_survey.json")
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
                (output / "hydrant-trace.jsonl").open("x", buffering=1) as trace:
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
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                                  "hydrant_actor_id": hydrant.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                extent = ego.bounding_box.extent
                trace.write(json.dumps({"source_kind": "original_native_observation",
                    "frame": frame, "native_frame": native_frame,
                    "video_frame": frame, "time_s": frame / 20,
                    "ego_actor_id": ego.id, "hydrant_actor_id": hydrant.id,
                    "ego_xyz_m": [pose.location.x, pose.location.y, pose.location.z],
                    "ego_extent_xyz_m": [extent.x, extent.y, extent.z],
                    "ego_yaw_deg": pose.rotation.yaw,
                    "ego_speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                    "hydrant_xyz_m": [hx, hy, hz],
                    "parking_permission_source": source["parking_permission_source"],
                    "hydrant_identity_source": source["hydrant_identity_source"],
                    "exception_context": config["exception_context"],
                    "exception_source_verified": False}) + "\n")
        for name in VIEWS:
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-framerate", "20", "-start_number", "0", "-i",
                       str(output / name / "%06d.png"), "-frames:v", "600",
                       "-an", "-c:v", "ffv1", "-threads", "1", str(output / (name + ".mkv"))]
            complete = subprocess.run(command, timeout=300, capture_output=True, text=True)
            encoder_codes[name] = complete.returncode
            require(complete.returncode == 0, "Camera encode failed: " + name)
    except BaseException as error:
        errors.append({"type": type(error).__name__, "message": str(error),
                       "traceback": traceback.format_exc()})
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
                 encoder_exit_codes=encoder_codes, context={"hydrant_survey_sha256":
                 hashlib.sha256((output / "hydrant_survey.json").read_bytes()).hexdigest()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--hydrant-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "Output directory required")
        execute(cfg, args.output_dir, args.hydrant_survey, args.host, args.port)
