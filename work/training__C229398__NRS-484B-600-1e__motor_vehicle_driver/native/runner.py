"""Unselected C229398 approach-to-curb Native feasibility draft.

The 85 mph value is a controller request, never a measured statutory outcome.
Execution requires an original surveyed route with room to brake and park.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
CASE = "training__C229398__NRS-484B-600-1e__motor_vehicle_driver__probe_03"
VIEWS = ("overview", "driver_front", "curb_side", "rear")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] == CASE and config["law_id"] == "NRS-484B-600-1e"
            and config["cell_id"] == "C229398" and config["actor"] == "motor_vehicle_driver",
            "exact assignment changed")
    require(config["frozen_cell"] == {"layout": "road", "maneuver": "park", "control": "curb"},
            "frozen cell changed")
    require(config["status"] == "unselected_native_feasibility_draft"
            and config["physical_completion"] is False and config["legal_verdict"] is None,
            "unproved outcome claimed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600,
            "30-second capture missing")
    require(config["requested_approach_speed_mph"] == 85, "request changed")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS
            and all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                    for c in config["cameras"]), "four-camera source plan incomplete")
    return {"case_id": CASE, "frame_count": 600, "rate_hz": 20,
            "views": list(VIEWS), "carla_contacted": False, "selected": False,
            "measured_speed_mph": None, "physical_completion": False}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey["source_kind"] == "original_native_curb_route_survey", "original route survey required")
    require(survey["map_name"] and survey["road_source_id"] and survey["curb_source_id"]
            and survey["approach_scope_source_id"] and survey["parking_scope_source_id"],
            "route and temporal scope sources missing")
    require(survey["cell_layout"] == "road" and survey["cell_maneuver"] == "park"
            and survey["cell_control"] == "curb", "survey does not establish fixed cell")
    require(len(survey["spawn_xyz_yaw_deg"]) == 4 and len(survey["curb_stop_xyz_m"]) == 3,
            "surveyed spawn or curb stop missing")
    require(0 < survey["approach_end_frame"] < survey["parking_end_frame"] < 600,
            "approach-to-park frame scopes missing")
    return survey


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original route survey required")
    survey = read_survey(survey_path)
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    repo = ROOT.parents[2]
    sys.path.insert(0, str(repo / "runtime" / "pipeline" / "scenario_pipeline"))
    sys.path.insert(1, str(repo / "runtime" / "pipeline" / "python"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    require(not output.exists(), "output directory already exists")
    output.mkdir(parents=True)
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors = [], []
    images = queue.Queue()
    try:
        require(world.get_map().name == survey["map_name"], "survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        vehicle_bp = library.find(survey["vehicle_blueprint"])
        require(vehicle_bp is not None, "vehicle blueprint unavailable")
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        vehicle = world.try_spawn_actor(vehicle_bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                                              carla.Rotation(yaw=yaw)))
        require(vehicle is not None, "surveyed vehicle spawn occupied")
        actors.append(vehicle)
        for camera in config["cameras"]:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=vehicle)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, vehicle, output, CASE, required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "native-speed.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose, velocity = vehicle.get_transform(), vehicle.get_velocity()
                observed_speed_mps = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                if frame < survey["approach_end_frame"]:
                    controller_phase = "approach_driving"
                    throttle = 0.7 if observed_speed_mps < config["requested_approach_speed_mph"] / 2.2369362920544 else 0.0
                    brake = 0.0
                elif frame < survey["parking_end_frame"]:
                    controller_phase = "curb_parking"
                    throttle, brake = 0.0, 0.8
                else:
                    controller_phase = "parked"
                    throttle, brake = 0.0, 1.0
                target = survey["curb_stop_xyz_m"]
                heading = math.atan2(target[1] - pose.location.y, target[0] - pose.location.x)
                relative = math.atan2(math.sin(heading - math.radians(pose.rotation.yaw)),
                                      math.cos(heading - math.radians(pose.rotation.yaw)))
                steer = max(-0.35, min(0.35, relative)) if controller_phase == "curb_parking" else 0.0
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                native_frame = world.tick()
                observed_pose, observed_velocity = vehicle.get_transform(), vehicle.get_velocity()
                observed_speed_after_mps = math.sqrt(observed_velocity.x**2 + observed_velocity.y**2
                                                     + observed_velocity.z**2)
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
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "vehicle_id": vehicle.id, "controller_phase": controller_phase,
                                        "phase_scope_source_id": survey["approach_scope_source_id"] if controller_phase == "approach_driving" else survey["parking_scope_source_id"],
                                        "velocity_xyz_mps": [observed_velocity.x, observed_velocity.y,
                                                             observed_velocity.z],
                                        "observed_speed_mph": observed_speed_after_mps * 2.2369362920544,
                                        "requested_speed_mph": config["requested_approach_speed_mph"],
                                        "position_xyz_m": [observed_pose.location.x, observed_pose.location.y,
                                                           observed_pose.location.z]}) + "\n")
    finally:
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restore(client, original)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--route-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "output directory required")
        execute(cfg, args.output_dir, args.route_survey or os.environ.get("SCENARIO_CURB_ROUTE_SURVEY"), args.host, args.port)
