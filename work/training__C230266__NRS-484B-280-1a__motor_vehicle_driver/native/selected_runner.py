"""Selected Native road-pedestrian encounter for two controlled responses."""

import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import threading
import traceback
from pathlib import Path

ASSIGNMENT = "training__C230266__NRS-484B-280-1a__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_90e3f1aa__condition_a": "distance_triggered_slow_request",
         ASSIGNMENT + "__selected_90e3f1aa__condition_b": "maintain_request"}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    require(config.get("case_id") in CASES and config.get("law_id") == "NRS-484B-280-1a"
            and config.get("cell_id") == "C230266"
            and config.get("actor") == "motor_vehicle_driver", "Wrong exact assignment")
    require(config.get("frozen_cell") == {"layout": "road", "maneuver": "travel",
                                          "control": "pedestrian"}, "Frozen cell changed")
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 30
            and config.get("frames") == 600, "Full 600-frame window required")
    cameras = config.get("cameras")
    require(isinstance(cameras, list) and tuple(c.get("name") for c in cameras) == VIEWS,
            "Four named source cameras required")
    require(cameras[0].get("width") == 1920 and cameras[0].get("height") == 1080,
            "Overview resolution changed")
    for camera in cameras:
        require(camera.get("fps") == 20 and camera.get("width", 0) >= 1280
                and camera.get("height", 0) >= 720
                and len(camera.get("location_xyz_m", [])) == 3
                and len(camera.get("rotation_pyr_deg", [])) == 3,
                "Camera rate, resolution or pose missing")
    require(config.get("physical_completion") is False and config.get("legal_verdict") is None,
            "Draft may not claim physical or legal outcome")
    require(config.get("controller") == CASES[config["case_id"]]
            and config.get("road_survey_required") is True
            and config.get("driver_observation_not_inferred_from_visibility") is True,
            "Source and controller policy changed")
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "source_views": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def read_survey(path):
    source = json.loads(Path(path).read_text())
    require(source.get("source_kind") == "original_native_road_survey"
            and source.get("map_name") and source.get("road_boundary_source")
            and source.get("vehicle_spawn_index") is not None
            and len(source.get("pedestrian_spawn_xyz_m", [])) == 3
            and len(source.get("pedestrian_path_end_xyz_m", [])) == 3
            and isinstance(source.get("pedestrian_walk_speed_mps"), (int, float))
            and 0 < source["pedestrian_walk_speed_mps"] <= 3
            and source.get("pedestrian_classification_source")
            and source.get("control_relationship_source")
            and type(source.get("pedestrian_crosses_vehicle_path")) is bool,
            "Original road and pedestrian survey missing")
    return source


def control(distance_m, speed_mps, mode):
    require(math.isfinite(distance_m) and math.isfinite(speed_mps)
            and speed_mps >= 0, "Measured distance and speed required")
    require(mode in CASES.values(), "Unknown controlled response")
    if mode == "distance_triggered_slow_request" and distance_m < 18:
        return {"throttle": 0.0, "brake": 0.45, "phase": "slow_request"}
    return {"throttle": 0.22, "brake": 0.0, "phase": "approach_request"}


def execute(config, output_dir, survey_path, host, port):
    check(config)
    survey_path = survey_path or os.environ.get("C230266_ROAD_SURVEY")
    require(survey_path is not None, "Original road survey required")
    source = read_survey(survey_path)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    require(output.is_dir() and (output / "config.json").is_file(),
            "Use a fresh exact-case materialized output")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors = [], []
    images = queue.Queue()
    collision_events = []
    collision_lock = threading.Lock()
    failure = None
    restoration = None
    cleanup_errors = []
    encoder_codes = {}
    try:
        require(world.get_map().name == source["map_name"], "Road survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        require(0 <= source["vehicle_spawn_index"] < len(spawns), "Vehicle spawn unavailable")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config["vehicle_blueprint"]),
                                    spawns[source["vehicle_spawn_index"]])
        require(ego is not None, "Vehicle spawn occupied")
        actors.append(ego)
        x, y, z = source["pedestrian_spawn_xyz_m"]
        ped = world.try_spawn_actor(world.get_blueprint_library().find(config["pedestrian_blueprint"]),
                                    carla.Transform(carla.Location(x=x, y=y, z=z)))
        require(ped is not None, "Pedestrian spawn occupied")
        actors.append(ped)
        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=ego)
        actors.append(collision_sensor)
        sensors.append(collision_sensor)

        def record_collision(event):
            with collision_lock:
                collision_events.append({"native_frame": event.frame,
                                         "other_actor_id": event.other_actor.id,
                                         "pedestrian_contact": event.other_actor.id == ped.id,
                                         "sensor_actor_id": collision_sensor.id})

        collision_sensor.listen(record_collision)
        shutil.copyfile(survey_path, output / "road_survey.json")
        end_x, end_y, _ = source["pedestrian_path_end_xyz_m"]
        path_length = math.hypot(end_x - x, end_y - y)
        require(path_length > 0.5, "Independent pedestrian path required")
        walk_direction = carla.Vector3D(x=(end_x - x) / path_length,
                                        y=(end_y - y) / path_length, z=0)
        for camera in config["cameras"]:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, yaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                                             carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)),
                                       attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "pedestrian-due-care-trace.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose = ego.get_transform()
                ped_pose = ped.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance = math.hypot(ped_pose.location.x - pose.location.x,
                                      ped_pose.location.y - pose.location.y)
                request = control(distance, speed, config["controller"])
                ego.apply_control(carla.VehicleControl(throttle=request["throttle"],
                                                       brake=request["brake"], steer=0.0))
                remaining = math.hypot(end_x - ped_pose.location.x, end_y - ped_pose.location.y)
                ped.apply_control(carla.WalkerControl(direction=walk_direction,
                                                      speed=source["pedestrian_walk_speed_mps"]
                                                      if remaining > 0.35 else 0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                                  "pedestrian_actor_id": ped.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                pose = ego.get_transform()
                ped_pose = ped.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                ped_speed = ped.get_velocity()
                trace.write(json.dumps({"source_kind": "original_native_observation",
                                        "frame": frame, "native_frame": native_frame,
                                        "video_frame": frame, "time_s": frame / 20,
                                        "ego_x_m": pose.location.x, "ego_y_m": pose.location.y,
                                        "ped_x_m": ped_pose.location.x,
                                        "ped_y_m": ped_pose.location.y,
                                        "ego_speed_mps": speed,
                                        "ped_speed_mps": math.hypot(ped_speed.x, ped_speed.y),
                                        "ego_actor_id": ego.id,
                                        "pedestrian_actor_id": ped.id,
                                        "vehicle_classification_source": config["vehicle_blueprint"],
                                        "pedestrian_classification_source": source["pedestrian_classification_source"],
                                        "control_relationship_source": source["control_relationship_source"],
                                        "vehicle_radius_m": math.hypot(ego.bounding_box.extent.x, ego.bounding_box.extent.y),
                                        "pedestrian_radius_m": math.hypot(ped.bounding_box.extent.x, ped.bounding_box.extent.y),
                                        "pedestrian_path_end_xyz_m": source["pedestrian_path_end_xyz_m"],
                                        "path_survey_source": source["road_boundary_source"],
                                        "path_conflict_survey": source["pedestrian_crosses_vehicle_path"],
                                        "contact_sensor_actor_id": collision_sensor.id,
                                        "contact_sensor_alive": collision_sensor.is_alive,
                                        "driver_observed_pedestrian": None,
                                        "driver_observation_source": None,
                                        "line_of_sight_clear": None,
                                        "requested_control": request}) + "\n")
        collision_sensor.stop()
        sensors.remove(collision_sensor)
        with collision_lock, (output / "contact_events.jsonl").open("x") as stream:
            for event in collision_events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
        for name in VIEWS:
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-framerate", "20", "-start_number", "0", "-i",
                       str(output / name / "%06d.png"), "-frames:v", "600",
                       "-an", "-c:v", "ffv1", "-threads", "1", str(output / (name + ".mkv"))]
            completed = subprocess.run(command, timeout=300, capture_output=True, text=True)
            encoder_codes[name] = completed.returncode
            require(completed.returncode == 0, "Camera encode failed: " + name + " " + completed.stderr[-500:])
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error),
                   "traceback": traceback.format_exc()}
        raise
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                cleanup_errors.append("sensor_stop: " + str(error))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                cleanup_errors.append("actor_destroy: " + str(error))
        try:
            restoration = restore(client, original)
        except BaseException as error:
            cleanup_errors.append("world_restore: " + str(error))
        if failure or cleanup_errors:
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": ([failure] if failure else []) + cleanup_errors,
                "restoration": restoration, "frames_expected": 600,
                "physical_acceptance_claimed": False}) + "\n")
            if cleanup_errors and not failure:
                raise RuntimeError("Native cleanup or restoration failed: " + "; ".join(cleanup_errors))
    try:
        seal_capture(output, frames=600, restoration=restoration, errors=[],
                     encoder_exit_codes=encoder_codes,
                     context={"road_survey_sha256": __import__("hashlib").sha256(
                         (output / "road_survey.json").read_bytes()).hexdigest()})
    except BaseException as error:
        (output / "native-run-status.json").write_text(json.dumps({
            "errors": ["capture_seal: " + str(error)], "restoration": restoration,
            "physical_acceptance_claimed": False}) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--road-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "Output directory required")
        execute(cfg, args.output_dir, args.road_survey, args.host, args.port)
