"""Exact 600-frame Native stop proposal for the paved-highway branch.

Only `--check` is used in CPU preparation. Execution requires an original
highway survey and an exclusively owned CARLA server.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
CASE = "training__C178965__NRS-484B-440-1__motor_vehicle_driver__probe_02"
VIEWS = ("overview", "ego_front", "roadside", "opposite_approach")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] == CASE, "case identity changed")
    require(config["law_id"] == "NRS-484B-440-1" and config["cell_id"] == "C178965"
            and config["actor"] == "motor_vehicle_driver", "assignment identity changed")
    require(config["frozen_cell"] == {"layout": "paved_road", "maneuver": "park", "control": "other_vehicle"}, "frozen cell changed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600, "30-second capture required")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS, "four-camera plan missing")
    require(all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                and len(c["location_xyz_m"]) == 3 and len(c["rotation_pyr_deg"]) == 3
                for c in config["cameras"]), "camera source configuration incomplete")
    require(config["physical_completion"] is False and config["legal_verdict"] is None, "unproved outcome claimed")
    return {"case_id": CASE, "frame_count": 600, "rate_hz": 20,
            "views": list(VIEWS), "carla_contacted": False, "physical_completion": False}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey["source_kind"] == "original_native_highway_survey", "original highway survey required")
    require(survey["map_name"] and survey["highway_source_id"] and survey["district_source_id"]
            and survey["pavement_edge_source_id"] and survey["offroad_area_source_id"]
            and survey["visibility_source_id"], "highway classification/geometry source missing")
    require(len(survey["spawn_xyz_yaw_deg"]) == 4 and len(survey["stop_target_xyz_m"]) == 3,
            "surveyed spawn or stop target missing")
    require(len(survey["other_spawn_xyz_yaw_deg"]) == 4, "other-vehicle spawn missing")
    require(survey["district"] == "outside", "survey is inside a business/residence district")
    return survey


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original highway survey required")
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
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        ego = world.try_spawn_actor(library.find(config["vehicle_blueprint"]),
                                    carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(ego is not None, "vehicle spawn occupied")
        actors.append(ego)
        ox, oy, oz, oyaw = survey["other_spawn_xyz_yaw_deg"]
        other = world.try_spawn_actor(library.find(config["vehicle_blueprint"]),
                                      carla.Transform(carla.Location(x=ox, y=oy, z=oz), carla.Rotation(yaw=oyaw)))
        require(other is not None, "other-vehicle spawn occupied")
        actors.append(other)
        for camera in config["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera["name"]).mkdir()
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, ego, output, CASE, required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "roadside-native.jsonl").open("x", buffering=1) as trace:
            for frame in range(600):
                pose, velocity = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = survey["stop_target_xyz_m"]
                dx, dy = target[0] - pose.location.x, target[1] - pose.location.y
                distance = math.hypot(dx, dy)
                heading = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
                heading = math.atan2(math.sin(heading), math.cos(heading))
                steer = max(-0.65, min(0.65, 1.1 * heading))
                target_speed = min(5.0, max(0.0, 0.5 * distance))
                throttle = max(0.0, min(0.5, 0.18 + 0.12 * (target_speed - speed))) if distance > 1 else 0.0
                brake = max(0.0, min(1.0, 0.25 * (speed - target_speed))) if distance > 1 else 1.0
                ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                other.apply_control(carla.VehicleControl(throttle=0.22, brake=0.0, steer=0.0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f"{frame:06d}.png"))
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame,
                                                               "other_vehicle_actor_id": other.id})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "vehicle_id": ego.id, "x_m": pose.location.x, "y_m": pose.location.y,
                                        "other_vehicle_id": other.id,
                                        "other_x_m": other.get_transform().location.x,
                                        "other_y_m": other.get_transform().location.y,
                                        "speed_mps": speed, "bbox_half_width_m": ego.bounding_box.extent.y,
                                        "target_distance_m": distance}) + "\n")
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
    parser.add_argument("--highway-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "output directory required")
        execute(cfg, args.output_dir, args.highway_survey or os.environ.get("SCENARIO_HIGHWAY_SURVEY"), args.host, args.port)
