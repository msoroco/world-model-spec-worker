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
import shutil
import sys

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "training__C178965__NRS-484B-440-1__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__probe_0" + str(i): mode for i, mode in
         ((1, "off_pavement"), (2, "on_pavement"), (3, "disabled_on_pavement"))}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] in CASES and config["stop_mode"] == CASES[config["case_id"]],
            "case identity changed")
    require(config["law_id"] == "NRS-484B-440-1" and config["cell_id"] == "C178965"
            and config["actor"] == "motor_vehicle_driver", "assignment identity changed")
    require(config["frozen_cell"] == {"layout": "paved_road", "maneuver": "park", "control": "other_vehicle"}, "frozen cell changed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600, "30-second capture required")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS, "four-camera plan missing")
    require(all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                and len(c["location_xyz_m"]) == 3 and len(c["rotation_pyr_deg"]) == 3
                for c in config["cameras"]), "camera source configuration incomplete")
    require(config["physical_completion"] is False and config["legal_verdict"] is None, "unproved outcome claimed")
    return {"case_id": config["case_id"], "frame_count": 600, "rate_hz": 20,
            "views": list(VIEWS), "carla_contacted": False, "physical_completion": False}


def validate_survey(survey):
    require(survey["source_kind"] == "original_native_highway_survey", "original highway survey required")
    require(survey["map_name"] and survey["highway_source_id"] and survey["district_source_id"]
            and survey["pavement_edge_source_id"] and survey["offroad_area_source_id"]
            and survey["visibility_source_id"], "highway classification/geometry source missing")
    require(len(survey["spawn_xyz_yaw_deg"]) == 4 and len(survey["stop_target_xyz_m"]) == 3,
            "surveyed spawn or stop target missing")
    require(len(survey["other_spawn_xyz_yaw_deg"]) == 4, "other-vehicle spawn missing")
    require(set(survey.get("stop_targets_xyz_m", {})) == set(CASES.values()),
            "all three surveyed stop targets required")
    require(all(len(target) == 3 for target in survey["stop_targets_xyz_m"].values()),
            "surveyed stop target coordinate missing")
    require(survey.get("disabled_failure_source_id"), "disabled failure source missing")
    require(survey["district"] == "outside", "survey is inside a business/residence district")
    require(survey.get("public_highway_reviewed") is True,
            "public highway classification remains unreviewed")
    require(survey.get("pavement_left_y_m") < survey.get("pavement_right_y_m"),
            "pavement edge coordinates missing")
    require(survey.get("vehicle_half_width_m", 0) > 0,
            "vehicle footprint width missing")
    require(set(survey.get("approach_visibility_sources", {})) == {"forward", "backward"},
            "both approach visibility sources required")
    require(all(isinstance(item, dict) and item.get("source_id") and
                item.get("path_distance_m", 0) >= 60.96 and
                len(item.get("location_xyz_m", [])) == 3
                for item in survey["approach_visibility_sources"].values()),
            "both approach visibility sources required")
    half = survey["vehicle_half_width_m"]
    left, right = survey["pavement_left_y_m"], survey["pavement_right_y_m"]
    off_y = survey["stop_targets_xyz_m"]["off_pavement"][1]
    on_y = survey["stop_targets_xyz_m"]["on_pavement"][1]
    disabled_y = survey["stop_targets_xyz_m"]["disabled_on_pavement"][1]
    require(off_y - half >= right or off_y + half <= left,
            "off-pavement stop target overlaps traveled pavement")
    require(left < on_y + half and on_y - half < right and
            left < disabled_y + half and disabled_y - half < right,
            "on-pavement stop targets miss traveled pavement")
    return survey


def read_survey(path):
    return validate_survey(json.loads(Path(path).read_text()))


def approach_rays(world, ego, survey, carla):
    """Nine original geometric rays from each surveyed 200-foot station."""
    targets = [ego.get_transform().location, *ego.bounding_box.get_world_vertices(ego.get_transform())]
    rays = {}
    for direction, source in survey["approach_visibility_sources"].items():
        x, y, z = source["location_xyz_m"]
        origin = carla.Location(x=x, y=y, z=z)
        clear = []
        for target in targets:
            hits = world.cast_ray(origin, target)
            # A hit at the target body is not an intervening obstruction.
            clear.append(not hits or hits[0].location.distance(target) <= 1.0)
        rays[direction] = {"source_id": source["source_id"],
                           "path_distance_m": source["path_distance_m"],
                           "ray_clear": clear}
    return rays


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original highway survey required")
    survey = read_survey(survey_path)
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    repo = ROOT.parents[2]
    sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
    sys.path.insert(1, str(repo / "runtime" / "python"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    if output.exists():
        require((output / "config.json").is_file(), "existing output lacks materialized config")
    else:
        output.mkdir(parents=True)
    shutil.copyfile(survey_path, output / "original-highway-survey.json")
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
        with PipelineCapture(client, ego, output, config["case_id"], required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "roadside-native.jsonl").open("x", buffering=1) as trace, \
                (output / "visibility-native.jsonl").open("x", buffering=1) as visibility:
            for frame in range(600):
                pose, velocity = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = survey["stop_targets_xyz_m"][config["stop_mode"]]
                dx, dy = target[0] - pose.location.x, target[1] - pose.location.y
                distance = math.hypot(dx, dy)
                heading = math.atan2(dy, dx) - math.radians(pose.rotation.yaw)
                heading = math.atan2(math.sin(heading), math.cos(heading))
                steer = max(-0.65, min(0.65, 1.1 * heading))
                target_speed = min(3.0, max(0.0, 0.35 * distance))
                throttle = max(0.0, min(0.4, 0.16 + 0.10 * (target_speed - speed))) if distance > 1 else 0.0
                brake = max(0.0, min(1.0, 0.40 * (speed - target_speed))) if distance > 1 else 1.0
                failure_active = config["stop_mode"] == "disabled_on_pavement" and distance <= 1.0
                if failure_active:
                    # Construct an engine-command failure, with the brake held.
                    # Original trace and geometry still decide whether departure was impossible.
                    throttle, brake, steer = 0.0, 1.0, 0.0
                    ego.set_light_state(carla.VehicleLightState(carla.VehicleLightState.LeftBlinker |
                                                                 carla.VehicleLightState.RightBlinker))
                # A held parking brake records the constructed parked/standing
                # episode; duration and attendance still require source review.
                parking_brake = distance <= 1.0
                ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake,
                                                       steer=steer, hand_brake=parking_brake))
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
                visibility.write(json.dumps({"source_kind": "original_native_raycast", "frame": frame,
                                             "native_frame": native_frame, "t_s": frame / 20,
                                             "approaches": approach_rays(world, ego, survey, carla)}) + "\n")
                pose, velocity = ego.get_transform(), ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance = math.hypot(target[0] - pose.location.x, target[1] - pose.location.y)
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "vehicle_id": ego.id, "x_m": pose.location.x, "y_m": pose.location.y,
                                        "other_vehicle_id": other.id,
                                        "other_x_m": other.get_transform().location.x,
                                        "other_y_m": other.get_transform().location.y,
                                        "speed_mps": speed, "bbox_half_width_m": ego.bounding_box.extent.y,
                                        "target_distance_m": distance, "stop_mode": config["stop_mode"],
                                        "parking_brake_commanded": parking_brake,
                                        "parking_brake_observed": ego.get_control().hand_brake,
                                        "failure_active": failure_active,
                                        "failure_source_id": survey["disabled_failure_source_id"] if failure_active else None}) + "\n")
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
    parser.add_argument("--case", choices=tuple(CASES))
    parser.add_argument("--highway-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    require(args.case is None or args.case == cfg["case_id"], "requested case differs from materialized construction")
    if args.check:
        print(json.dumps(check(cfg)))
    else:
        require(args.output_dir, "output directory required")
        execute(cfg, args.output_dir, args.highway_survey or os.environ.get("SCENARIO_HIGHWAY_SURVEY"), args.host, args.port)
