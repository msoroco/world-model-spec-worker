"""Exact Native bicycle driveway-sidewalk crossing proposal.

CPU `--check` does not contact CARLA. Execution requires a surveyed continuous
sidewalk, rider blueprint confirmation and an exclusively owned CARLA server.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
CASE = "training__C213851__LVMC-11-40-140__cycle_or_scooter_operator__probe_01"
VIEWS = ("overview", "rider_front", "sidewalk_side", "pedestrian_side")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] == CASE, "exact case changed")
    require(config["law_id"] == "LVMC-11-40-140" and config["cell_id"] == "C213851"
            and config["actor"] == "cycle_or_scooter_operator", "assignment changed")
    require(config["frozen_cell"] == {"layout": "residence_district", "maneuver": "exit_road",
                                       "control": "driveway_entrance"}, "frozen cell changed")
    require(config["rider_blueprint"] == "vehicle.bh.crossbike" and config["rider_class"] == "bicycle",
            "rider class or blueprint changed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600,
            "30-second capture missing")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS, "four cameras required")
    require(all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                and len(c["location_xyz_m"]) == 3 and len(c["rotation_pyr_deg"]) == 3
                for c in config["cameras"]), "camera source plan incomplete")
    require(config["physical_completion"] is False and config["legal_verdict"] is None,
            "unproved outcome claimed")
    return {"case_id": CASE, "frame_count": 600, "rate_hz": 20,
            "views": list(VIEWS), "carla_contacted": False, "physical_completion": False}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey["source_kind"] == "original_native_sidewalk_survey", "original sidewalk survey required")
    require(survey["map_name"] and survey["district_source_id"] and survey["driveway_source_id"]
            and survey["sidewalk_continuation_source_id"] and survey["sidewalk_boundary_source_id"]
            and survey["rider_blueprint_source_id"], "district/sidewalk/rider survey missing")
    require(survey["district"] == "residence" and survey["origin_kind"] == "driveway"
            and survey["sidewalk_continuation_across_driveway"] is True, "selected branch survey differs")
    require(len(survey["rider_spawn_xyz_yaw_deg"]) == 4 and len(survey["pedestrian_spawn_xyz_yaw_deg"]) == 4
            and len(survey["pre_sidewalk_stop_xyz_m"]) == 3 and len(survey["after_sidewalk_xyz_m"]) == 3,
            "surveyed spawns or route missing")
    require(len(survey["pedestrian_direction_xyz"]) == 3 and survey["pedestrian_speed_mps"] >= 0,
            "pedestrian controller survey missing")
    return survey


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original sidewalk survey required")
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
    if output.exists():
        require((output / "config.json").is_file(), "existing output lacks materialized config")
    else:
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
        require(library.find(config["rider_blueprint"]) is not None, "rider blueprint unavailable")
        x, y, z, yaw = survey["rider_spawn_xyz_yaw_deg"]
        rider = world.try_spawn_actor(library.find(config["rider_blueprint"]),
                                      carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(rider is not None, "rider spawn occupied")
        actors.append(rider)
        x, y, z, yaw = survey["pedestrian_spawn_xyz_yaw_deg"]
        pedestrian = world.try_spawn_actor(library.find(config["pedestrian_blueprint"]),
                                           carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(pedestrian is not None, "pedestrian spawn occupied")
        actors.append(pedestrian)
        for camera in config["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=rider)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, rider, output, CASE, required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "sidewalk-native.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose, velocity = rider.get_transform(), rider.get_velocity()
                ped_pose = pedestrian.get_transform()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = survey["pre_sidewalk_stop_xyz_m"] if frame < 260 else survey["after_sidewalk_xyz_m"]
                dx, dy = target[0] - pose.location.x, target[1] - pose.location.y
                distance = math.hypot(dx, dy)
                heading = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
                heading = math.atan2(math.sin(heading), math.cos(heading))
                steer = max(-0.6, min(0.6, heading))
                if 180 <= frame < 260:
                    throttle, brake = 0.0, 1.0
                else:
                    throttle, brake = (0.3, 0.0) if speed < 3 else (0.0, 0.15)
                rider.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                pedestrian.apply_control(carla.WalkerControl(direction=carla.Vector3D(*survey["pedestrian_direction_xyz"]), speed=survey["pedestrian_speed_mps"]))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                               "pedestrian_actor_id": pedestrian.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "rider_id": rider.id, "pedestrian_id": pedestrian.id,
                                        "rider_x_m": pose.location.x, "rider_y_m": pose.location.y,
                                        "rider_speed_mps": speed,
                                        "pedestrian_x_m": ped_pose.location.x,
                                        "pedestrian_y_m": ped_pose.location.y,
                                        "requested_stop_phase": 180 <= frame < 260}) + "\n")
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
    parser.add_argument("--sidewalk-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "output directory required")
        execute(cfg, args.output_dir, args.sidewalk_survey or os.environ.get("SCENARIO_SIDEWALK_SURVEY"), args.host, args.port)
