"""Template for an exact NRS 484B.280(1)(c) Native construction.

The builder replaces the three tokens below for each case. A map survey is an
execution input, not a substitute for original capture or legal review.
"""

import argparse
import hashlib
import json
import math
import os
import queue
import subprocess
from pathlib import Path

CASE = "training__C230266__NRS-484B-280-1c__motor_vehicle_driver__transit_stop_maintain"
BRANCH = "transit_stop"
MODE = "maintain"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CONTEXT_KEYS = {
    "road": ("road_boundary_source", "pedestrian_position_source"),
    "bus_stop": ("bus_stop_designation_source", "bus_stop_geometry_source", "pedestrian_position_source"),
    "bench": ("bench_geometry_source", "bench_public_mass_transport_use_source", "pedestrian_position_source"),
    "shelter": ("shelter_geometry_source", "shelter_public_mass_transport_use_source", "pedestrian_position_source"),
    "transit_stop": ("stop_designation_source", "stop_furniture_geometry_source", "pedestrian_position_source"),
    "boarding": ("transit_vehicle_class_source", "door_side_source", "boarding_motion_source"),
    "other_transport": ("other_public_transport_class_source", "door_side_source", "boarding_motion_source"),
    "school_zone": ("school_zone_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "school_crossing": ("school_crossing_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "marked_crosswalk": ("marked_crosswalk_source", "pedestrian_position_source"),
    "unmarked_crosswalk": ("intersection_and_sidewalk_source", "unmarked_crossing_limits_source", "pedestrian_position_source"),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    require(config.get("case_id") == CASE and config.get("law_id") == "NRS-484B-280-1c"
            and config.get("cell_id") == "C230266"
            and config.get("actor") == "motor_vehicle_driver", "Wrong exact assignment")
    require(config.get("frozen_cell") == {"layout": "road", "maneuver": "travel",
                                          "control": "pedestrian"}, "Frozen cell changed")
    require(config.get("branch") == BRANCH and config.get("mode") == MODE,
            "Wrong statutory branch or comparison mode")
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
    require(config.get("driver_observation_not_inferred_from_visibility") is True,
            "Actual observation policy changed")
    require(config.get("controller") == ("distance_triggered_slow_request" if MODE == "caution"
                                         else "maintain_approach_request"),
            "Comparison controller changed")
    return {"case_id": CASE, "branch": BRANCH, "mode": MODE, "frames": 600,
            "rate_hz": 20, "source_views": list(VIEWS), "carla_contacted": False,
            "physical_completion": False, "legal_verdict": None}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey.get("source_kind") == "original_native_context_survey"
            and survey.get("map_name") and survey.get("vehicle_spawn_index") is not None
            and len(survey.get("pedestrian_spawn_xyz_m", [])) == 3
            and survey.get("pedestrian_classification_source")
            and survey.get("control_relationship_source"),
            "Original Native map, actor and relationship survey missing")
    for key in CONTEXT_KEYS[BRANCH]:
        require(isinstance(survey.get(key), str) and survey[key].strip(),
                "Missing original " + key)
    if BRANCH in ("bus_stop", "bench", "shelter", "transit_stop", "school_zone", "school_crossing"):
        require(survey.get("context_prop_blueprint") and
                len(survey.get("context_prop_xyz_m", [])) == 3,
                "Surveyed physical context prop missing")
    if BRANCH in ("boarding", "other_transport"):
        require(survey.get("transit_vehicle_blueprint") and
                len(survey.get("transit_vehicle_xyz_m", [])) == 3
                and len(survey.get("boarding_waypoints_xyz_m", [])) >= 2,
                "Transit vehicle and boarding path construction missing")
    if BRANCH in ("marked_crosswalk", "unmarked_crosswalk"):
        require(len(survey.get("crossing_polygon_xyz_m", [])) >= 4,
                "Surveyed physical crossing polygon missing")
        if BRANCH == "marked_crosswalk":
            require(survey.get("marked_crossing_visible_source"),
                    "Original visible markings source missing")
    if BRANCH in ("boarding", "other_transport", "marked_crosswalk", "unmarked_crosswalk"):
        require(len(survey.get("pedestrian_path_xyz_m", [])) >= 2,
                "Pedestrian crossing or boarding path missing")
    return survey


def control(distance_m, speed_mps):
    require(math.isfinite(distance_m) and math.isfinite(speed_mps)
            and speed_mps >= 0, "Measured distance and speed required")
    if MODE == "caution" and distance_m < 18:
        return {"throttle": 0.0, "brake": 0.45, "phase": "slow_request"}
    return {"throttle": 0.22, "brake": 0.0, "phase": "approach_request"}


def spawn_context(world, carla, survey, actors):
    """Place surveyed objects; source claims stay separate from actor geometry."""
    library = world.get_blueprint_library()
    if BRANCH in ("bus_stop", "bench", "shelter", "transit_stop", "school_zone", "school_crossing"):
        xyz = survey["context_prop_xyz_m"]
        actor = world.try_spawn_actor(library.find(survey["context_prop_blueprint"]),
                                      carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2])))
        require(actor is not None, "Surveyed context prop spawn failed")
        actors.append(actor)
    if BRANCH in ("boarding", "other_transport"):
        xyz = survey["transit_vehicle_xyz_m"]
        actor = world.try_spawn_actor(library.find(survey["transit_vehicle_blueprint"]),
                                      carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2])))
        require(actor is not None, "Surveyed transit vehicle spawn failed")
        actors.append(actor)
    return [actor.id for actor in actors[2:]]


def pedestrian_target(survey, frame):
    path = survey.get("pedestrian_path_xyz_m")
    if not path:
        return None
    start, end = path[0], path[-1]
    fraction = max(0.0, min(1.0, (frame - 160) / 120))
    return [start[axis] + fraction * (end[axis] - start[axis]) for axis in range(3)]


def execute(config, output_dir, survey_path, host, port):
    check(config)
    survey_path = survey_path or os.environ.get("SCENARIO_CONTEXT_SURVEY")
    require(survey_path is not None, "Original Native context survey required")
    survey = read_survey(survey_path)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    # runtime.py capture materializes the inline bundle in this directory first.
    output.mkdir(parents=True, exist_ok=True)
    survey_bytes = Path(survey_path).read_bytes()
    with (output / "context-survey.json").open("xb") as preserved_survey:
        preserved_survey.write(survey_bytes)
    survey_sha256 = hashlib.sha256(survey_bytes).hexdigest()
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoders, encoder_codes = [], [], {}, {}
    images = queue.Queue()
    completed = False
    try:
        require(world.get_map().name == survey["map_name"], "Native survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        index = survey["vehicle_spawn_index"]
        require(type(index) is int and 0 <= index < len(spawns), "Vehicle spawn unavailable")
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config["vehicle_blueprint"]),
                                    spawns[index])
        require(ego is not None, "Vehicle spawn occupied")
        actors.append(ego)
        x, y, z = survey["pedestrian_spawn_xyz_m"]
        ped = world.try_spawn_actor(world.get_blueprint_library().find(config["pedestrian_blueprint"]),
                                    carla.Transform(carla.Location(x=x, y=y, z=z)))
        require(ped is not None, "Pedestrian spawn occupied")
        actors.append(ped)
        context_ids = spawn_context(world, carla, survey, actors)
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
            encoders[camera["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f"{camera['width']}x{camera['height']}",
                "-r", "20", "-i", "-", "-frames:v", "600",
                "-c:v", "ffv1", "-level", "1",
                str(output / (camera["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, CASE,
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "pedestrian-caution-trace.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                target = pedestrian_target(survey, frame)
                if target is not None:
                    ped.set_transform(carla.Transform(carla.Location(x=target[0], y=target[1], z=target[2])))
                pose = ego.get_transform()
                ped_pose = ped.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance = math.hypot(ped_pose.location.x - pose.location.x,
                                      ped_pose.location.y - pose.location.y)
                request = control(distance, speed)
                ego.apply_control(carla.VehicleControl(throttle=request["throttle"],
                                                       brake=request["brake"], steer=0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    encoders[name].stdin.write(image.raw_data)
                    seen.add(name)
                pose = ego.get_transform()
                ped_pose = ped.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                                  "pedestrian_actor_id": ped.id,
                                                                  "context_actor_ids": context_ids})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_pose_and_control",
                                        "branch": BRANCH, "frame": frame,
                                        "ego_actor_id": ego.id,
                                        "pedestrian_actor_id": ped.id,
                                        "context_survey_sha256": survey_sha256,
                                        "native_frame": native_frame, "video_frame": frame,
                                        "time_s": frame / 20,
                                        "ego_x_m": pose.location.x, "ego_y_m": pose.location.y,
                                        "ped_x_m": ped_pose.location.x, "ped_y_m": ped_pose.location.y,
                                        "ego_speed_mps": speed,
                                        "driver_observed_pedestrian": None,
                                        "driver_observation_source": None,
                                        "line_of_sight_clear": None,
                                        "branch_position_evidenced": None,
                                        "requested_control": request}) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            require(encoder_codes[name] == 0 and (output / (name + ".mkv")).is_file(),
                    "Original camera encode failed: " + name + " " + error.decode()[-200:])
        completed = True
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restored = restore(client, original)
        if completed and len(encoder_codes) == 4:
            seal_capture(output, frames=600, restoration=restored, errors=[],
                         encoder_exit_codes=encoder_codes, context={"case_id": CASE})
            record_native_exit(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--context-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "Output directory required")
        execute(cfg, args.output_dir, args.context_survey, args.host, args.port)
