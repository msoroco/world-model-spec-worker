"""Prospective four-camera Native capture for visible vehicle preparation.

An original map/actor survey is mandatory at execution. CPU tests exercise the
plan and controller; they cannot certify CARLA motion, lights, or pixels.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import hashlib

HERE = Path(__file__).resolve().parent
ASSIGNMENT_ID = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver"
BASE = ASSIGNMENT_ID + "__preparing_to_move__"
CONDITIONS = {BASE + "visible_vehicle_movement": "visible_vehicle_movement"}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
RATE = 20
FRAMES = 600


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_config(config):
    case = config.get("case_id")
    require(case in CONDITIONS and config.get("selected_case_id") == case,
            "Exact case identity changed")
    require((config.get("law_id"), config.get("cell_id"), config.get("actor")) ==
            ("NRS-484B-267-2a", "C405647", "motor_vehicle_driver"),
            "Frozen assignment identity changed")
    require((config.get("rate_hz"), config.get("duration_frames"), config.get("duration_s")) ==
            (RATE, FRAMES, 30), "Exact duration changed")
    require(tuple(view.get("name") for view in config.get("cameras", [])) == VIEWS,
            "Four original cameras required")
    require(all(view.get("fps") == RATE and view.get("width", 0) >= 1280
                and view.get("height", 0) >= 720 for view in config["cameras"]),
            "Camera profile differs")
    require(config.get("activation_branch") == CONDITIONS[case]
            and config.get("ego_initial_speed_mps") == 14
            and config.get("ego_target_speed_mps") == 7
            and config.get("other_vehicle_start_frame") in (100, 120)
            and config.get("other_vehicle_speed_mps") == 1,
            "Visible vehicle movement intervention changed")
    return {"case_id": config["case_id"], "frames": FRAMES, "views": list(VIEWS),
            "native_executed": False, "site_survey_pending": True,
            "physical_completion_claimed": False}


def check(config, survey):
    check_config(config)
    require(survey.get("source_kind") == "original_native_site_survey"
            and survey.get("cell") == {"layout": "road", "maneuver": "travel",
                                       "control": "emergency_vehicle"},
            "Original same-cell road survey required")
    require(survey.get("map_name") and survey.get("ego_blueprint")
            and survey.get("emergency_blueprint")
            and len(survey.get("ego_spawn_xyz_yaw_deg", [])) == 4
            and len(survey.get("emergency_spawn_xyz_yaw_deg", [])) == 4,
            "Original map and two actor spawns required")
    ego_spawn = survey["ego_spawn_xyz_yaw_deg"]
    other_spawn = survey["emergency_spawn_xyz_yaw_deg"]
    require(other_spawn[0] - ego_spawn[0] > 120
            and abs(ego_spawn[1] - other_spawn[1]) < 3.5
            and all(abs(spawn[3]) <= 15 for spawn in (ego_spawn, other_spawn)),
            "Surveyed approach direction or road alignment differs")
    for key in ("emergency_authorization_source_id", "flashing_equipment_source_id",
                "flashing_qualification_source_id", "road_context_source_id",
                "weather_context_source_id", "officer_direction_source_id"):
        require(survey.get(key), "Original qualification or context source missing: " + key)
    require(survey.get("officer_direction") is None, "Officer direction is a separate branch")
    camera_poses = survey.get("camera_poses", {})
    require(set(camera_poses) == set(VIEWS)
            and all(len(camera_poses[name]) == 6 for name in VIEWS),
            "Four original camera extrinsics required")
    return {"case_id": config["case_id"], "frames": FRAMES, "views": list(VIEWS),
            "native_executed": False, "physical_completion_claimed": False}


def speed_control(target_mps, measured_mps):
    """Simple bounded longitudinal request; targets are not legal cutoffs."""
    require(math.isfinite(target_mps) and math.isfinite(measured_mps)
            and target_mps >= 0 and measured_mps >= 0, "Speed input must be finite")
    error = target_mps - measured_mps
    return {"throttle": min(0.55, max(0.0, 0.20 * error)),
            "brake": min(0.65, max(0.0, -0.20 * error))}


def _speed(velocity):
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def _transform(value, carla):
    x, y, z, yaw = value
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))


def camera_encode_command(output, name):
    require(name in VIEWS, "Unknown original camera")
    folder = Path(output)
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
            "-framerate", str(RATE), "-start_number", "0", "-i",
            str(folder / name / "%06d.png"), "-frames:v", str(FRAMES),
            "-an", "-c:v", "ffv1", "-pix_fmt", "yuv444p",
            str(folder / (name + ".mkv"))]


def execute(config, survey, output_dir, host, port, *, diagnostic_fixture=False):
    check(config, survey)
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    repo = HERE.parents[2]
    sys.path.insert(0, str(repo / "runtime"))
    sys.path.insert(1, str(repo / "runtime" / "python"))
    import carla
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap
    from scenario_pipeline.worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    require(not (output / "capture").exists(), "Use a fresh Native attempt path")
    output.mkdir(parents=True, exist_ok=True)
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture" if diagnostic_fixture else "native",
        "diagnostic_fixture": diagnostic_fixture,
        "case_id": config["case_id"],
        "site_survey_sha256": hashlib.sha256(json.dumps(survey, sort_keys=True).encode()).hexdigest(),
        "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors = []
    sensors = []
    images = queue.Queue()
    restoration = None
    try:
        require(world.get_map().name == survey["map_name"], "Survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        spawned = []
        for role in ("ego", "emergency"):
            blueprint = blueprints.find(survey[role + "_blueprint"])
            require(blueprint is not None, "Surveyed actor blueprint unavailable: " + role)
            actor = world.try_spawn_actor(blueprint,
                                          _transform(survey[role + "_spawn_xyz_yaw_deg"], carla))
            require(actor is not None, "Surveyed actor spawn occupied: " + role)
            actors.append(actor)
            spawned.append(actor)
        ego, emergency = spawned
        special_lights = carla.VehicleLightState.Special1 | carla.VehicleLightState.Special2
        for view in config["cameras"]:
            name = view["name"]
            blueprint = blueprints.find("sensor.camera.rgb")
            require(blueprint is not None, "RGB camera blueprint unavailable")
            blueprint.set_attribute("image_size_x", str(view["width"]))
            blueprint.set_attribute("image_size_y", str(view["height"]))
            blueprint.set_attribute("sensor_tick", str(1 / RATE))
            x, y, z, pitch, yaw, roll = survey["camera_poses"][name]
            pose = carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            sensor = world.spawn_actor(blueprint, pose, attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / name).mkdir()
            sensor.listen(lambda image, view_name=name: images.put((view_name, image)))
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config.get("required_atoms", [])) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "preparing_observations.jsonl").open("x", buffering=1) as trace:
            for index in range(FRAMES):
                emergency.set_light_state(special_lights if (index // 10) % 2 == 0 else 0)
                target = config["ego_target_speed_mps"] if index >= 160 else config["ego_initial_speed_mps"]
                controls = speed_control(target, _speed(ego.get_velocity()))
                ego.apply_control(carla.VehicleControl(throttle=controls["throttle"],
                                                       brake=controls["brake"], steer=0.0))
                other_target = (config["other_vehicle_speed_mps"]
                                if index >= config["other_vehicle_start_frame"] else 0)
                other_controls = speed_control(other_target,
                                               _speed(emergency.get_velocity()))
                emergency.apply_control(carla.VehicleControl(throttle=other_controls["throttle"],
                                                             brake=other_controls["brake"], steer=0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{index:06d}.png"))
                    seen.add(name)
                ego_pose, other_pose = ego.get_transform(), emergency.get_transform()
                ego_velocity, other_velocity = ego.get_velocity(), emergency.get_velocity()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds
                frame_map.append(native_frame, index / RATE, native_elapsed_s=elapsed)
                capture.capture(native_frame, index / RATE,
                                extra={"video_frame": index, "emergency_actor_id": emergency.id})
                trace.write(json.dumps({
                    "case_id": config["case_id"],
                    "source_kind": "synthetic_cpu_fixture" if diagnostic_fixture else "original_native_observation",
                    "video_frame": index, "native_frame": native_frame, "time_s": index / RATE,
                    "ego": {"actor_id": ego.id, "road_x_m": ego_pose.location.x,
                            "position_xyz_m": [ego_pose.location.x, ego_pose.location.y, ego_pose.location.z],
                            "speed_mps": _speed(ego_velocity)},
                    "qualifying_vehicle": {"actor_id": emergency.id,
                                           "road_x_m": other_pose.location.x,
                                           "position_xyz_m": [other_pose.location.x, other_pose.location.y,
                                                              other_pose.location.z],
                                           "speed_mps": _speed(other_velocity),
                                           "kind": "authorized_emergency_vehicle",
                                           "authorized_source_id": survey["emergency_authorization_source_id"],
                                           "flashing_state": bool(int(emergency.get_light_state()) & int(special_lights)),
                                           "lamp_equipment_source_id": survey["flashing_equipment_source_id"],
                                           "lamp_qualification_source_id": survey["flashing_qualification_source_id"]},
                    "officer_direction": None,
                    "officer_direction_source_id": survey["officer_direction_source_id"],
                    "already_moving": False,
                    "visible_vehicle_movement": index >= config["other_vehicle_start_frame"]
                    and _speed(other_velocity) > 0.05,
                    "visible_driver_hand_signal": False,
                    "hand_signal_driver_actor_id": None,
                    "road_context_source_id": survey["road_context_source_id"],
                    "weather_context_source_id": survey["weather_context_source_id"],
                    "posted_limit_mps": config["posted_limit_mps"],
                    "visibility_m": config["visibility_m"], "wet_road": config["wet_road"],
                    "camera_frames": {name: native_frame for name in VIEWS}
                }, sort_keys=True, allow_nan=False) + "\n")
    finally:
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restoration = restore(client, original)
    if diagnostic_fixture:
        return
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from scenario_pipeline.worker_exchange.media import compose_four_views
    sources = {}
    for name in VIEWS:
        subprocess.run(camera_encode_command(output, name), check=True, timeout=3600)
        sources[name] = output / (name + ".mkv")
    compose_four_views(sources, output / "video_frames.jsonl", output / "primary.mkv")
    seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in VIEWS},
                 context={"case_id": config["case_id"],
                          "site_survey_sha256": hashlib.sha256(json.dumps(survey, sort_keys=True).encode()).hexdigest(),
                          "physical_acceptance_claimed": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--survey", required=True)
    parser.add_argument("--output")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    configuration = json.loads(Path(arguments.config).read_text())
    site = json.loads(Path(arguments.survey).read_text())
    if arguments.check:
        print(json.dumps(check(configuration, site), sort_keys=True))
    else:
        require(arguments.output, "Native output path required")
        execute(configuration, site, arguments.output, arguments.host, arguments.port)
