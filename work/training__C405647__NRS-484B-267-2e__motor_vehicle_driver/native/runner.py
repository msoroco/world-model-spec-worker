"""Unselected C405647 moving-emergency move-over Native feasibility draft.

Survey supplies lane topology, authorization and lamp qualification sources.
Controller requests are distinct from measured occupancy, safety and duty.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
CASE = "training__C405647__NRS-484B-267-2e__motor_vehicle_driver__probe_01"
VIEWS = ("overview", "driver_front", "emergency_side", "rear")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] == CASE and config["law_id"] == "NRS-484B-267-2e"
            and config["cell_id"] == "C405647" and config["actor"] == "motor_vehicle_driver",
            "exact assignment changed")
    require(config["frozen_cell"] == {"layout": "road", "maneuver": "travel",
                                      "control": "emergency_vehicle"}, "frozen cell changed")
    require(config["status"] == "unselected_native_feasibility_draft"
            and config["requested_maneuver"] == "move_to_nonadjacent_lane"
            and config["physical_completion"] is False and config["legal_verdict"] is None,
            "unproved outcome claimed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600,
            "30-second capture missing")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS
            and all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                    for c in config["cameras"]), "four-camera source plan incomplete")
    return {"case_id": CASE, "frame_count": 600, "views": list(VIEWS),
            "carla_contacted": False, "selected": False, "feasibility_verified": False}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey.get("source_kind") == "original_native_emergency_lane_survey",
            "original lane survey required")
    require(survey.get("fixed_cell") == {"layout": "road", "maneuver": "travel",
                                         "control": "emergency_vehicle"}, "survey cell mismatch")
    require(survey.get("map_name") and survey.get("lane_topology_source_id")
            and survey.get("emergency_authorization_source_id")
            and survey.get("flashing_equipment_source_id")
            and survey.get("flashing_qualification_source_id")
            and survey.get("roadway_condition_source_id")
            and survey.get("traffic_condition_source_id")
            and survey.get("weather_condition_source_id")
            and survey.get("officer_direction_source_id"),
            "emergency, lane or exception sources missing")
    require(len(survey.get("ego_spawn_xyz_yaw_deg", [])) == 4
            and len(survey.get("emergency_spawn_xyz_yaw_deg", [])) == 4
            and len(survey.get("nonadjacent_target_xyz_m", [])) == 3
            and survey.get("ego_blueprint") and survey.get("emergency_blueprint"),
            "surveyed actors or nonadjacent route missing")
    require(survey.get("emergency_lane_id") and survey.get("adjacent_ego_lane_id")
            and survey.get("nonadjacent_ego_lane_id")
            and len({survey["emergency_lane_id"], survey["adjacent_ego_lane_id"],
                     survey["nonadjacent_ego_lane_id"]}) == 3,
            "three distinct lane identities required")
    return survey


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original emergency-lane survey required")
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
        spawned = []
        for prefix in ("ego", "emergency"):
            bp = library.find(survey[prefix + "_blueprint"])
            require(bp is not None, prefix + " blueprint unavailable")
            x, y, z, yaw = survey[prefix + "_spawn_xyz_yaw_deg"]
            actor = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                                              carla.Rotation(yaw=yaw)))
            require(actor is not None, prefix + " spawn occupied")
            actors.append(actor)
            spawned.append(actor)
        ego, emergency = spawned
        emergency.set_light_state(carla.VehicleLightState.Special1 | carla.VehicleLightState.Special2)
        for camera in config["cameras"]:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, CASE, required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "emergency-native.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose, velocity = ego.get_transform(), ego.get_velocity()
                target = survey["nonadjacent_target_xyz_m"]
                heading = math.atan2(target[1] - pose.location.y, target[0] - pose.location.x)
                relative = math.atan2(math.sin(heading - math.radians(pose.rotation.yaw)),
                                      math.cos(heading - math.radians(pose.rotation.yaw)))
                steer = max(-0.4, min(0.4, relative))
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                ego.apply_control(carla.VehicleControl(throttle=0.35 if speed < 8 else 0.0,
                                                       brake=0.0 if speed < 8 else 0.1, steer=steer))
                emergency.apply_control(carla.VehicleControl(throttle=0.25, steer=0.0))
                native_frame = world.tick()
                observed_pose, observed_velocity = ego.get_transform(), ego.get_velocity()
                emergency_pose, emergency_velocity = emergency.get_transform(), emergency.get_velocity()
                ego_waypoint = world.get_map().get_waypoint(observed_pose.location, project_to_road=False)
                emergency_waypoint = world.get_map().get_waypoint(emergency_pose.location, project_to_road=False)
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                               "emergency_actor_id": emergency.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "ego_id": ego.id, "emergency_id": emergency.id,
                                        "ego_position_xyz_m": [observed_pose.location.x, observed_pose.location.y,
                                                               observed_pose.location.z],
                                        "ego_velocity_xyz_mps": [observed_velocity.x, observed_velocity.y,
                                                                 observed_velocity.z],
                                        "emergency_position_xyz_m": [emergency_pose.location.x,
                                                                     emergency_pose.location.y,
                                                                     emergency_pose.location.z],
                                        "emergency_velocity_xyz_mps": [emergency_velocity.x,
                                                                       emergency_velocity.y,
                                                                       emergency_velocity.z],
                                        "ego_map_lane_id": ego_waypoint.lane_id if ego_waypoint else None,
                                        "emergency_map_lane_id": emergency_waypoint.lane_id if emergency_waypoint else None,
                                        "flashing_light_state": int(emergency.get_light_state()),
                                        "requested_move_over": True,
                                        "approach_verified": False,
                                        "feasibility_verified": False}) + "\n")
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
    parser.add_argument("--lane-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, "output directory required")
        execute(config, args.output_dir, args.lane_survey or os.environ.get("SCENARIO_EMERGENCY_LANE_SURVEY"),
                args.host, args.port)
